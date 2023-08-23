from collections import Counter
import csv
from datetime import timedelta
import json
import logging
from typing import Iterable

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.signing import BadSignature, TimestampSigner
from django.http.request import HttpRequest
from django.http.response import Http404, HttpResponse
from django.shortcuts import render
from ninja import Query, Router
from ninja.errors import AuthenticationError
from ninja.security import APIKeyQuery

from isic.core.models import CopyrightLicense, Image
from isic.core.pagination import CursorPagination
from isic.core.serializers import SearchQueryIn
from isic.core.services import _image_metadata_csv_headers, image_metadata_csv_rows

logger = logging.getLogger(__name__)
zip_router = Router()


# this is directly mirrored in isic-cli
def get_attributions(attributions: Iterable[str]) -> list[str]:
    counter = Counter(attributions)
    # sort by the number of images descending, then the name of the institution ascending
    attributions = sorted(counter.most_common(), key=lambda v: (-v[1], v[0]))
    # push anonymous attributions to the end
    attributions = sorted(attributions, key=lambda v: 1 if v[0] == "Anonymous" else 0)
    return [x[0] for x in attributions]


class ZipDownloadTokenAuth(APIKeyQuery):
    param_name = "token"

    def authenticate(self, request: HttpRequest, key: str) -> dict:
        try:
            token_dict = TimestampSigner().unsign_object(key, max_age=timedelta(days=1))
        except BadSignature:
            logger.exception("Bad zip download token passed")
            raise AuthenticationError

        token_dict["token"] = key
        return token_dict


@zip_router.post("/url/", response=str, include_in_schema=False)
def create_zip_download_url(request: HttpRequest, payload: SearchQueryIn):
    token = TimestampSigner().sign_object(payload.to_token_representation(user=request.user))
    return f"{settings.ZIP_DOWNLOAD_SERVICE_URL}/download?zsid={token}"


@zip_router.get("/file-listing/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_listing(
    request: HttpRequest,
    pagination: CursorPagination.Input = Query(...),
):
    token = request.auth["token"]
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession"))

    paginator = CursorPagination()
    # confusingly, the first page will have a page size of at least paginator.page_size + 2.
    # this is because the first page will have the metadata and attribution files and
    # it's easier to just include them in the first page than to try to override
    # the paginator's behavior.
    resp_data = paginator.paginate_queryset(qs, pagination, request)

    files = [
        {"url": image.accession.blob.url, "zipPath": f"{image.isic_id}.JPG"}
        for image in resp_data["results"]
    ]

    # initialize files with metadata and attribution files
    if resp_data["previous"] is None:
        logger.info(
            f"Creating zip file descriptor for {qs.count()} images: " f"{json.dumps(request.auth)}"
        )
        domain = Site.objects.get_current().domain
        files += [
            {
                "url": f"http://{domain}/api/v2/zip-download/metadata-file/?token={token}",
                "zipPath": "metadata.csv",
            },
            {
                "url": f"http://{domain}/api/v2/zip-download/attribution-file/?token={token}",
                "zipPath": "attribution.txt",
            },
        ]

        files += [
            {
                "url": f"http://{domain}/api/v2/zip-download/license-file/{license}",
                "zipPath": f"licenses/{license}.txt",
            }
            for license in (
                qs.values_list("accession__copyright_license", flat=True).order_by().distinct()
            )
        ]

    resp_data["results"] = files
    return resp_data


@zip_router.get("/metadata-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_metadata_file(request: HttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    response = HttpResponse(content_type="text/csv")
    writer = csv.DictWriter(response, _image_metadata_csv_headers(qs=qs))
    writer.writeheader()

    for metadata_row in image_metadata_csv_rows(qs=qs):
        writer.writerow(metadata_row)

    return response


@zip_router.get("/attribution-file/", include_in_schema=False, auth=ZipDownloadTokenAuth())
def zip_file_attribution_file(request: HttpRequest):
    user, search = SearchQueryIn.from_token_representation(request.auth)
    qs = search.to_queryset(user, Image.objects.select_related("accession__cohort").distinct())
    attributions = get_attributions(qs.values_list("accession__cohort__attribution", flat=True))
    return HttpResponse("\n\n".join(attributions), content_type="text/plain")


@zip_router.get("/license-file/{license_type}/", include_in_schema=False)
def zip_file_license_file(request: HttpRequest, license_type: str):
    if license_type not in CopyrightLicense.values:
        raise Http404

    return render(request, f"zip_download/{license_type}.txt", content_type="text/plain")
