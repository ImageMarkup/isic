from collections import Counter
from collections.abc import Generator, Iterable
from datetime import timedelta
from itertools import batched
import json
import logging
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.core.files.storage import default_storage, storages
from django.core.signing import BadSignature, TimestampSigner
from django.db import connection, transaction
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.http.response import Http404, HttpResponse
from django.shortcuts import render
from django.urls import path, reverse
import orjson
from rest_framework.authentication import BaseAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from isic.core.models import CopyrightLicense, Image
from isic.core.serializers import SearchQueryBodySerializer, SearchQuerySerializer
from isic.core.services import image_metadata_csv
from isic.core.utils.csv import EscapingDictWriter
from isic.core.utils.http import Echo

if TYPE_CHECKING:
    from urllib.parse import ParseResult

logger = logging.getLogger(__name__)

ZIP_LISTING_BATCH_SIZE = 256


# this is directly mirrored in isic-cli
def get_attributions(attributions: Iterable[str]) -> list[str]:
    counter = Counter(attributions)
    # sort by the number of images descending, then the name of the institution ascending
    attributions = sorted(counter.most_common(), key=lambda v: (-v[1], v[0]))  # type: ignore  # noqa: PGH003
    # push anonymous attributions to the end
    attributions = sorted(attributions, key=lambda v: 1 if v[0] == "Anonymous" else 0)
    return [x[0] for x in attributions]


class ZipDownloadTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        key = request.query_params.get("token")
        if not key:
            raise AuthenticationFailed

        try:
            token_dict = TimestampSigner().unsign_object(key, max_age=timedelta(days=1))
        except BadSignature:
            raise AuthenticationFailed from None

        token_dict["token"] = key
        return AnonymousUser(), token_dict


@api_view(["POST"])
@permission_classes([AllowAny])
def zip_download_url(request):
    payload = SearchQueryBodySerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    url: ParseResult | None = settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL
    if url is None:
        raise ValueError("ISIC_ZIP_DOWNLOAD_SERVICE_URL is not set.")

    token = TimestampSigner().sign_object(payload.to_token_representation(user=request.user))
    return Response(f"{url.scheme}://{url.netloc}" + f"/download?zsid={token}")


def _zip_file_listing_generator(qs: QuerySet[Image], token: str) -> Generator[dict[str, str]]:
    def extension_from_str(s: str) -> str:
        return PurePosixPath(s).suffix.lstrip(".")

    for image in (
        qs.values("accession__blob", "accession__sponsored_blob", "public", "isic_id")
        .order_by()
        .iterator()
    ):
        if image["public"]:
            url = storages["sponsored"].unsigned_url(image["accession__sponsored_blob"])
            zip_path = (
                f"{image['isic_id']}.{extension_from_str(image['accession__sponsored_blob'])}"
            )
        else:
            url = default_storage.unsigned_url(image["accession__blob"])
            zip_path = f"{image['isic_id']}.{extension_from_str(image['accession__blob'])}"

        yield {
            "url": url,
            "zipPath": zip_path,
        }

    # initialize files with metadata and attribution files
    domain = Site.objects.get_current().domain
    for endpoint, zip_path in [
        [reverse("api:zip_download_metadata_file"), "metadata.csv"],
        [reverse("api:zip_download_attribution_file"), "attribution.txt"],
    ]:
        yield {
            "url": f"http://{domain}{endpoint}?token={token}",
            "zipPath": zip_path,
        }

    yield from (
        {
            "url": f"http://{domain}{reverse('api:zip_download_license_file', args=[license_])}",
            "zipPath": f"licenses/{license_}.txt",
        }
        for license_ in (
            qs.values_list("accession__copyright_license", flat=True).order_by().distinct()
        )
    )


def _write_file_listing(
    suggested_filename: str, files: Iterable[dict[str, str]]
) -> Generator[bytes]:
    yield b'{"suggestedFilename": ' + orjson.dumps(suggested_filename) + b', "files": ['

    has_preceding_element = False
    # yield entries in batches, since responding with many small chunks incurs per-chunk
    # overhead in the WSGI write path and socket writes.
    for file_batch in batched(files, ZIP_LISTING_BATCH_SIZE, strict=False):
        chunk: list[bytes] = []
        for file in file_batch:
            if has_preceding_element:
                chunk.append(b",")
            has_preceding_element = True
            chunk.append(orjson.dumps({"url": file["url"], "zipPath": file["zipPath"]}))
        yield b"".join(chunk)

    yield b"]}"


@api_view(["GET"])
@authentication_classes([ZipDownloadTokenAuthentication])
@permission_classes([AllowAny])
@transaction.atomic
def zip_download_listing(request):
    # use repeatable read to ensure consistent results
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

    token = request.auth["token"]
    user, search = SearchQuerySerializer.from_token_representation(request.auth)

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

    return StreamingHttpResponse(
        _write_file_listing(suggested_filename, files), content_type="application/json"
    )


@api_view(["GET"])
@authentication_classes([ZipDownloadTokenAuthentication])
@permission_classes([AllowAny])
def zip_download_metadata_file(request):
    user, search = SearchQuerySerializer.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())

    fieldnames, metadata_rows = image_metadata_csv(qs=qs)

    def write_response() -> Generator[bytes]:
        writer = EscapingDictWriter(Echo(), fieldnames)
        yield writer.writeheader()

        for metadata_row in metadata_rows:
            yield writer.writerow(metadata_row)

    return StreamingHttpResponse(write_response(), content_type="text/csv")


@api_view(["GET"])
@authentication_classes([ZipDownloadTokenAuthentication])
@permission_classes([AllowAny])
def zip_download_attribution_file(request):
    user, search = SearchQuerySerializer.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    attributions = get_attributions(qs.values_list("accession__attribution", flat=True))
    return HttpResponse("\n\n".join(attributions), content_type="text/plain")


@api_view(["GET"])
@permission_classes([AllowAny])
def zip_download_license_file(request, license_type: str):
    if license_type not in CopyrightLicense.values:
        raise Http404

    return render(request, f"zip_download/{license_type}.txt", content_type="text/plain")


urlpatterns = [
    path("url/", zip_download_url, name="zip_download_url"),
    path("file-listing/", zip_download_listing, name="zip_download_listing"),
    path("metadata-file/", zip_download_metadata_file, name="zip_download_metadata_file"),
    path(
        "attribution-file/",
        zip_download_attribution_file,
        name="zip_download_attribution_file",
    ),
    path(
        "license-file/<license_type>/",
        zip_download_license_file,
        name="zip_download_license_file",
    ),
]
