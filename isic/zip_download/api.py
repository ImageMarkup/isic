from collections import Counter
from collections.abc import Generator, Iterable
from datetime import timedelta
from itertools import batched
import json
import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.contrib.sites.models import Site
from django.core.files.storage import storages
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

if TYPE_CHECKING:
    from urllib.parse import ParseResult

logger = logging.getLogger(__name__)

ZIP_LISTING_BATCH_SIZE = 256
# rows fetched from the server side cursor at a time, about 100 bytes each
ZIP_LISTING_CHUNK_SIZE = 20_000


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


def _zip_file_listing_generator(qs: QuerySet[Image], auth: dict) -> Generator[dict[str, str]]:
    sponsored_storage = storages["sponsored"]
    private_storage = storages["default"]
    licenses: set[str] = set()
    file_count = 0

    rows = (
        qs.values_list(
            "accession__blob",
            "accession__sponsored_blob",
            "public",
            "isic_id",
            "accession__copyright_license",
        )
        .order_by()
        .iterator(chunk_size=ZIP_LISTING_CHUNK_SIZE)
    )
    for blob, sponsored_blob, public, isic_id, copyright_license in rows:
        file_count += 1
        licenses.add(copyright_license)
        if public:
            storage, name = sponsored_storage, sponsored_blob
        else:
            storage, name = private_storage, blob
        # the same as PurePosixPath(name).suffix, but saves about 1 second per million entries
        stem, dot, extension = name.rpartition("/")[2].rpartition(".")
        yield {
            "url": storage.unsigned_url(name),
            "zipPath": f"{isic_id}.{extension if dot and stem else ''}",
        }

    logger.info("Listed %d images for zip download: %s", file_count, json.dumps(auth))

    domain = Site.objects.get_current().domain
    for endpoint, zip_path in [
        [reverse("api:zip_download_metadata_file"), "metadata.csv"],
        [reverse("api:zip_download_attribution_file"), "attribution.txt"],
    ]:
        yield {
            "url": f"http://{domain}{endpoint}?token={auth['token']}",
            "zipPath": zip_path,
        }

    for license_ in sorted(licenses):
        yield {
            "url": f"http://{domain}{reverse('api:zip_download_license_file', args=[license_])}",
            "zipPath": f"licenses/{license_}.txt",
        }


def _write_file_listing(qs: QuerySet[Image], auth: dict) -> Generator[bytes]:
    # the response streams after the view returns, so the transaction is opened here instead of
    # around the view
    with transaction.atomic():
        with connection.cursor() as cursor:
            # the filename check and the listing read the same snapshot
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            # django reads the listing through a server side cursor (DECLARE ... CURSOR), and
            # postgres assumes a cursor fetches only cursor_tuple_fraction (default 0.1) of its
            # rows, so it plans for a cheap first row instead of a cheap full result. the listing
            # always fetches every row, and at a million images the first-row plan took 7 seconds
            # against 1.
            cursor.execute("SET LOCAL cursor_tuple_fraction = 1.0")

        isic_ids = list(qs.values_list("isic_id", flat=True)[:2])
        suggested_filename = f"{isic_ids[0]}.zip" if len(isic_ids) == 1 else "ISIC-images.zip"
        yield b'{"suggestedFilename": ' + orjson.dumps(suggested_filename) + b', "files": ['

        has_preceding_element = False
        # yield entries in batches, since responding with many small chunks incurs per-chunk
        # overhead in the WSGI write path and socket writes.
        for file_batch in batched(
            _zip_file_listing_generator(qs, auth), ZIP_LISTING_BATCH_SIZE, strict=False
        ):
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
def zip_download_listing(request):
    user, search = SearchQuerySerializer.from_token_representation(request.auth)

    # ordering isn't necessary for the zipstreamer and can slow down the query considerably
    qs = search.to_queryset(user, Image.objects.all()).order_by()

    return StreamingHttpResponse(
        _write_file_listing(qs, request.auth), content_type="application/json"
    )


@api_view(["GET"])
@authentication_classes([ZipDownloadTokenAuthentication])
@permission_classes([AllowAny])
def zip_download_metadata_file(request):
    user, search = SearchQuerySerializer.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())

    _, csv_rows = image_metadata_csv(qs=qs)

    return StreamingHttpResponse(csv_rows, content_type="text/csv")


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
