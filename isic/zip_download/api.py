from collections import Counter
from collections.abc import Iterable
import csv
from datetime import UTC, datetime, timedelta
import json
import logging
from pathlib import PurePosixPath

from botocore.signers import CloudFrontSigner
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.files.storage import default_storage
from django.core.signing import BadSignature, TimestampSigner
from django.db import connection, transaction
from django.http.request import HttpRequest
from django.http.response import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from ninja import Router
from ninja.errors import AuthenticationError
from ninja.security import APIKeyQuery, HttpBasicAuth
import rsa

from isic.core.models import CopyrightLicense, Image
from isic.core.serializers import SearchQueryIn
from isic.core.services import image_metadata_csv
from isic.types import NinjaAuthHttpRequest

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
    def authenticate(self, request, username, password):
        if username == "" and constant_time_compare(
            password, settings.ZIP_DOWNLOAD_BASIC_AUTH_TOKEN
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


@zip_router.post("/url/", response=str, include_in_schema=False)
def create_zip_download_url(request: HttpRequest, payload: SearchQueryIn):
    token = TimestampSigner().sign_object(payload.to_token_representation(user=request.user))
    return f"{settings.ZIP_DOWNLOAD_SERVICE_URL}/download?zsid={token}"


create_zip_download_url.csrf_exempt = True  # type: ignore[attr-defined]


def _cloudfront_signer(message: bytes) -> bytes:
    # See the documentation for CloudFrontSigner
    return rsa.sign(
        message,
        rsa.PrivateKey.load_pkcs1(default_storage.cloudfront_key.encode("utf8")),
        "SHA-1",
    )


@zip_router.get("/file-listing/", include_in_schema=False, auth=zip_api_auth)
@transaction.atomic
def zip_file_listing(
    request: NinjaAuthHttpRequest,
):
    def extension_from_str(s: str) -> str:
        return PurePosixPath(s).suffix.lstrip(".")

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

    if settings.ZIP_DOWNLOAD_WILDCARD_URLS:
        # this is a performance optimization. repeated signing of individual urls
        # is slow when generating large descriptors. this allows generating one signature and
        # using it for all urls.
        signer = CloudFrontSigner(default_storage.cloudfront_key_id, _cloudfront_signer)
        # create a wildcard signature that allows access to * and pass this to the zipstreamer.
        # since zip_api_auth uses a shared secret that only it and the zipstreamer know, this
        # can't be intercepted by someone looking at the zipstreamer url.
        url = f"https://{default_storage.custom_domain}/*"
        policy = signer.build_policy(
            url,
            date_less_than=datetime.now(tz=UTC) + timedelta(days=1),
        )
        signed_url = signer.generate_presigned_url(url, policy=policy)
        files = [
            {
                "url": signed_url.replace("*", image["accession__blob"]),
                "zipPath": f"{image['isic_id']}.{extension_from_str(image['accession__blob'])}",
            }
            for image in qs.values("accession__blob", "isic_id").iterator()
        ]
    else:
        # development doesn't have any cloudfront frontend so we need to sign each individual url.
        # this is considerably slower because of the signing and the hydrating of the related
        # objects instead of being able to utilize .values.
        files = [
            {
                "url": image.accession.blob.url,
                "zipPath": f"{image.isic_id}.{image.extension}",
            }
            for image in qs.iterator()
        ]

    # initialize files with metadata and attribution files
    logger.info(
        "Creating zip file descriptor for %d images: %s",
        file_count,
        json.dumps(request.auth),
    )
    domain = Site.objects.get_current().domain
    for endpoint, zip_path in [
        [reverse("api:zip_file_metadata_file"), "metadata.csv"],
        [reverse("api:zip_file_attribution_file"), "attribution.txt"],
    ]:
        files.append(
            {
                "url": f"http://{domain}{endpoint}?token={token}",
                "zipPath": zip_path,
            }
        )

    files += [
        {
            "url": f"http://{domain}{reverse('api:zip_file_license_file', args=[license_])}",
            "zipPath": f"licenses/{license_}.txt",
        }
        for license_ in (
            qs.values_list("accession__copyright_license", flat=True).order_by().distinct()
        )
    ]

    return {
        "suggestedFilename": suggested_filename,
        "files": files,
    }


@zip_router.get("/metadata-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_metadata_file(request: NinjaAuthHttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    response = HttpResponse(content_type="text/csv")

    metadata_file = image_metadata_csv(qs=qs)
    writer = csv.DictWriter(response, next(metadata_file))
    writer.writeheader()

    for metadata_row in metadata_file:
        assert isinstance(metadata_row, dict)  # noqa: S101
        writer.writerow(metadata_row)

    return response


@zip_router.get("/attribution-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_attribution_file(request: NinjaAuthHttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    attributions = get_attributions(
        qs.values_list("accession__cohort__default_attribution", flat=True)
    )
    return HttpResponse("\n\n".join(attributions), content_type="text/plain")


@zip_router.get("/license-file/{license_type}/", include_in_schema=False)
def zip_file_license_file(request: HttpRequest, license_type: str):
    if license_type not in CopyrightLicense.values:
        raise Http404

    return render(request, f"zip_download/{license_type}.txt", content_type="text/plain")
