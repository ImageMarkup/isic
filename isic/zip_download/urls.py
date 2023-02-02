from django.urls import path

from isic.zip_download.api import (
    create_zip_download_url,
    zip_file_attribution_file,
    zip_file_descriptor,
    zip_file_metadata_file,
)

urlpatterns = [
    path(
        "api/v2/zip-download/url/",
        create_zip_download_url,
        name="zip-download/api/url",
    ),
    path(
        "api/v2/zip-download/file-descriptor/",
        zip_file_descriptor,
        name="zip-download/api/file-descriptor",
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
]
