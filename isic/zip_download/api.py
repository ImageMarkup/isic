from collections import Counter
from collections.abc import Generator, Iterable
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Literal

from botocore.signers import CloudFrontSigner
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files.storage import default_storage, storages
from django.core.signing import BadSignature, TimestampSigner
from django.db import connection, transaction
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.http.request import HttpRequest
from django.http.response import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from ninja import Router
from ninja.errors import AuthenticationError
from ninja.security import APIKeyQuery, HttpBasicAuth
import orjson
import rsa

from isic.core.models import CopyrightLicense, Image
from isic.core.serializers import SearchQueryIn
from isic.core.services import image_metadata_csv
from isic.core.utils.csv import EscapingDictWriter
from isic.core.utils.http import Buffer
from isic.types import NinjaAuthHttpRequest

if TYPE_CHECKING:
    from urllib.parse import ParseResult

logger = logging.getLogger(__name__)
zip_router = Router()


# this is directly mirrored in isic-cli
def get_attributions(attributions: Iterable[str]) -> list[str]:
    counter = Counter(attributions)
    # sort by the number of images descending, then the name of the institution ascending
    attributions = sorted(counter.most_common(), key=lambda v: (-v[1], v[0]))  # type: ignore  # noqa: PGH003
    # push anonymous attributions to the end
    attributions = sorted(attributions, key=lambda v: 1 if v[0] == "Anonymous" else 0)
    return [x[0] for x in attributions]


class ZipDownloadBasicAuth(HttpBasicAuth):
    def authenticate(self, request: HttpRequest, username: str, password: str) -> Literal[True]:
        if username == "" and constant_time_compare(
            password, settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL.password
        ):
            return True

        raise AuthenticationError


class ZipDownloadTokenAuth(APIKeyQuery):
    param_name = "token"

    def authenticate(self, request: HttpRequest, key: str | None) -> dict:
        if not key:
            raise AuthenticationError

        try:
            token_dict = TimestampSigner().unsign_object(key, max_age=timedelta(days=1))
        except BadSignature:
            raise AuthenticationError from None

        token_dict["token"] = key
        return token_dict


def zip_api_auth(request: HttpRequest):
    """
    Protects the zip listing endpoint with basic auth.

    This requires both basic auth and a valid token auth. The basic auth credential is shared
    with the zipstreamer service and can't be intercepted. This is necessary because the signed
    URLs from zip_file_listing are wildcard signed, so they grant access to all files in the bucket.
    Without an additional layer of security, anyone who can see the zipstreamer url could download
    any file in the bucket.
    """
    # the default auth argument for ninja routes checks if ANY of the backends validate,
    # but we want to check that ALL of them validate.
    if not ZipDownloadBasicAuth()(request):
        return False

    return ZipDownloadTokenAuth()(request)


@csrf_exempt
@zip_router.post("/url/", response=str, include_in_schema=False)
def create_zip_download_url(request: HttpRequest, payload: SearchQueryIn):
    url: ParseResult | None = settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL
    if url is None:
        raise ValueError("ISIC_ZIP_DOWNLOAD_SERVICE_URL is not set.")

    token = TimestampSigner().sign_object(payload.to_token_representation(user=request.user))
    return (
        f"{url.scheme}://{url.hostname}"
        + (f":{url.port}" if url.port else "")
        + f"/download?zsid={token}"
    )


def _cloudfront_signer(message: bytes) -> bytes:
    # See the documentation for CloudFrontSigner
    return rsa.sign(
        message,
        rsa.PrivateKey.load_pkcs1(default_storage.cloudfront_key.encode("utf8")),
        "SHA-1",
    )


def _zip_file_listing_generator(qs: QuerySet[Image], token: str) -> Generator[dict[str, str]]:
    def extension_from_str(s: str) -> str:
        return PurePosixPath(s).suffix.lstrip(".")

    if settings.ISIC_ZIP_DOWNLOAD_WILDCARD_URLS:
        # this is a performance optimization. repeated signing of individual urls
        # is slow when generating large descriptors. this allows generating one signature and
        # using it for all urls.
        signer = CloudFrontSigner(default_storage.cloudfront_key_id, _cloudfront_signer)
        # create a wildcard signature that allows access to * and pass this to the zipstreamer.
        # since zip_api_auth uses a shared secret that only it and the zipstreamer know, this
        # can't be intercepted by someone looking at the zipstreamer url.
        bucket_url = f"https://{default_storage.custom_domain}/*"
        policy = signer.build_policy(
            bucket_url,
            date_less_than=datetime.now(tz=UTC) + timedelta(days=1),
        )
        signed_url = signer.generate_presigned_url(bucket_url, policy=policy)
        for image in (
            qs.values("accession__blob", "accession__sponsored_blob", "public", "isic_id")
            .order_by()
            .iterator()
        ):
            if image["public"]:
                # storages['sponsored'].url still goes through all of the presigning logic which
                # significantly slows things down.
                url = f"https://{storages['sponsored'].bucket_name}.s3.amazonaws.com/{image['accession__sponsored_blob']}"
                zip_path = (
                    f"{image['isic_id']}.{extension_from_str(image['accession__sponsored_blob'])}"
                )
            else:
                url = signed_url.replace("*", image["accession__blob"])
                zip_path = f"{image['isic_id']}.{extension_from_str(image['accession__blob'])}"

            yield {
                "url": url,
                "zipPath": zip_path,
            }

    else:
        # development doesn't have any cloudfront frontend so we need to sign each individual url.
        # this is considerably slower because of the signing and the hydrating of the related
        # objects instead of being able to utilize .values.
        yield from (
            {
                "url": image.blob.url,
                # image.extension requires downloading the blob, so use extension_from_str.
                "zipPath": f"{image.isic_id}.{extension_from_str(image.blob.name)}",
            }
            for image in qs.select_related("accession", "isic")
            .only("public", "isic", "accession__blob", "accession__sponsored_blob")
            .order_by()
            .iterator()
        )

    # initialize files with metadata and attribution files
    domain = Site.objects.get_current().domain
    for endpoint, zip_path in [
        [reverse("api:zip_file_metadata_file"), "metadata.csv"],
        [reverse("api:zip_file_attribution_file"), "attribution.txt"],
    ]:
        yield {
            "url": f"http://{domain}{endpoint}?token={token}",
            "zipPath": zip_path,
        }

    yield from (
        {
            "url": f"http://{domain}{reverse('api:zip_file_license_file', args=[license_])}",
            "zipPath": f"licenses/{license_}.txt",
        }
        for license_ in (
            qs.values_list("accession__copyright_license", flat=True).order_by().distinct()
        )
    )


@zip_router.get("/file-listing/", include_in_schema=False, auth=zip_api_auth)
@transaction.atomic
def zip_file_listing(
    request: NinjaAuthHttpRequest,
):
    # use repeatable read to ensure consistent results
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    token = request.auth["token"]
    user, search = SearchQueryIn.from_token_representation(request.auth)

    # ordering isn't necessary for the zipstreamer and can slow down the query considerably
    qs = search.to_queryset(user, Image.objects.select_related("accession")).order_by()
    file_count = qs.count()
    if file_count == 1:
        only_image = qs.first()
        assert isinstance(only_image, Image)  # noqa: S101
        suggested_filename = f"{only_image.isic_id}.zip"
    else:
        suggested_filename = "ISIC-images.zip"

    logger.info(
        "Creating zip file descriptor for %d images: %s",
        file_count,
        json.dumps(request.auth),
    )
    files = _zip_file_listing_generator(qs, token)

    def write_response(buffer: Buffer) -> Iterable[bytes]:
        yield f'{{"suggestedFilename": "{suggested_filename}", "files": ['.encode()

        has_preceding_element = False
        for file in files:
            if has_preceding_element:
                yield b","
            has_preceding_element = True
            # orjson yields a 7-10x performance improvement over json.dumps
            yield orjson.dumps({"url": file["url"], "zipPath": file["zipPath"]})

        yield b"]}"

    return StreamingHttpResponse(write_response(Buffer()), content_type="application/json")


@zip_router.get("/metadata-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_metadata_file(request: NinjaAuthHttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())

    metadata_file = image_metadata_csv(qs=qs)

    def write_response(buffer: Buffer) -> Iterable[bytes]:
        writer = EscapingDictWriter(buffer, next(metadata_file))
        yield writer.writeheader()

        for metadata_row in metadata_file:
            assert isinstance(metadata_row, dict)  # noqa: S101
            yield writer.writerow(metadata_row)

    return StreamingHttpResponse(write_response(Buffer()), content_type="text/csv")


@zip_router.get("/attribution-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_attribution_file(request: NinjaAuthHttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    attributions = get_attributions(qs.values_list("accession__attribution", flat=True))
    return HttpResponse("\n\n".join(attributions), content_type="text/plain")


@zip_router.get("/license-file/{license_type}/", include_in_schema=False)
def zip_file_license_file(request: HttpRequest, license_type: str):
    if license_type not in CopyrightLicense.values:
        raise Http404

    return render(request, f"zip_download/{license_type}.txt", content_type="text/plain")
