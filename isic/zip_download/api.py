from collections import Counter
import csv
from datetime import timedelta
import logging
from typing import Iterable

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.signing import BadSignature, TimestampSigner
from django.http.response import HttpResponse, JsonResponse
from django.urls.base import reverse
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from isic.core.models.image import Image
from isic.core.serializers import SearchQuerySerializer
from isic.core.services import _image_metadata_csv_headers, image_metadata_csv_rows
from isic.zip_download.serializers import ZipFileDescriptorSerializer

logger = logging.getLogger(__name__)


# this is directly mirrored in isic-cli
def get_attributions(attributions: Iterable[str]) -> list[str]:
    counter = Counter(attribution for attribution in attributions)
    # sort by the number of images descending, then the name of the institution ascending
    attributions = sorted(counter.most_common(), key=lambda v: (-v[1], v[0]))
    # push anonymous attributions to the end
    attributions = sorted(attributions, key=lambda v: 1 if v[0] == "Anonymous" else 0)
    return [x[0] for x in attributions]


def get_zip_download_token(token: str | None = None) -> dict:
    if not token:
        raise PermissionDenied

    signer = TimestampSigner()

    try:
        # TODO: do we sign tokens longer than URLs?
        return signer.unsign_object(token, max_age=timedelta(days=1))
    except BadSignature:
        raise PermissionDenied


@swagger_auto_schema(methods=["POST"], auto_schema=None)
@api_view(["POST"])
@permission_classes([AllowAny])
def create_zip_download_url(request):
    serializer = SearchQuerySerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)

    token = TimestampSigner().sign_object(serializer.to_token_representation())

    return Response(f"{settings.ZIP_DOWNLOAD_SERVICE_URL}/download?zsid={token}")


@swagger_auto_schema(methods=["GET"], auto_schema=None)
@api_view(["GET"])
@permission_classes([AllowAny])
def zip_file_descriptor(request):
    token = request.query_params.get("token")
    download_info = get_zip_download_token(token)
    serializer = SearchQuerySerializer.from_token_representation(download_info)
    serializer.is_valid(raise_exception=True)

    logger.info(
        f"Creating zip file descriptor for {serializer.to_queryset().count()} images",
        extra={"download_info": download_info},
    )

    descriptor = {
        "suggestedFilename": "isic-data.zip",
        "files": [
            {
                "url": f"http://{Site.objects.get_current().domain}"
                + reverse("zip-download/api/metadata-file")
                + f"?token={token}",
                "zipPath": "metadata.csv",
            },
            {
                "url": f"http://{Site.objects.get_current().domain}"
                + reverse("zip-download/api/attribution-file")
                + f"?token={token}",
                "zipPath": "attribution.txt",
            },
        ],
    }

    qs = serializer.to_queryset(Image.objects.select_related("accession"))
    for image in qs.iterator():
        descriptor["files"].append(
            {
                "url": image.accession.blob.url,
                "zipPath": f"{image.isic_id}.JPG",
            }
        )
    return JsonResponse(ZipFileDescriptorSerializer(descriptor).data)


@swagger_auto_schema(methods=["GET"], auto_schema=None)
@api_view(["GET"])
@permission_classes([AllowAny])
def zip_file_metadata_file(request):
    download_info = get_zip_download_token(request.query_params.get("token"))
    serializer = SearchQuerySerializer.from_token_representation(download_info)
    serializer.is_valid(raise_exception=True)

    qs = serializer.to_queryset(Image.objects.select_related("accession__cohort").distinct())
    response = HttpResponse(content_type="text/csv")
    writer = csv.DictWriter(response, _image_metadata_csv_headers(qs=qs))
    writer.writeheader()

    for metadata_row in image_metadata_csv_rows(qs=qs):
        writer.writerow(metadata_row)

    return response


@swagger_auto_schema(methods=["GET"], auto_schema=None)
@api_view(["GET"])
@permission_classes([AllowAny])
def zip_file_attribution_file(request):
    download_info = get_zip_download_token(request.query_params.get("token"))
    serializer = SearchQuerySerializer.from_token_representation(download_info)
    serializer.is_valid(raise_exception=True)

    qs = serializer.to_queryset(Image.objects.select_related("accession__cohort").distinct())
    attributions = get_attributions(qs.values_list("accession__cohort__attribution", flat=True))
    return HttpResponse("\n\n".join(attributions), content_type="text/plain")
