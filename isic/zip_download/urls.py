from django.urls import path

from isic.zip_download.api import (
    create_zip_download_url,
    zip_file_attribution_file,
    zip_file_license_file,
    zip_file_listing,
    zip_file_metadata_file,
)

urlpatterns = [
    path(
        "api/v2/zip-download/url/",
        create_zip_download_url,
        name="zip-download/api/url",
    ),
    path(
        "api/v2/zip-download/file-listing/",
        zip_file_listing,
        name="zip-download/api/file-listing",
    ),
    path(
        "api/v2/zip-download/metadata-file/",
        zip_file_metadata_file,
        name="zip-download/api/metadata-file",
    ),
    path(
        "api/v2/zip-download/attribution-file/",
        zip_file_attribution_file,
        name="zip-download/api/attribution-file",
    ),
    path(
        "api/v2/zip-download/license-file/<str:license_type>/",
        zip_file_license_file,
        name="zip-download/api/license-file",
    ),
]
