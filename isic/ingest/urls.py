from django.urls import path

from isic.ingest.views.accession import accession_cog_viewer
from isic.ingest.views.cohort import cohort_detail, cohort_list, cohort_merge, cohort_publish
from isic.ingest.views.metadata import apply_metadata, metadata_file_create, metadata_file_detail
from isic.ingest.views.review import cohort_review, ingest_review
from isic.ingest.views.upload import (
    cohort_files,
    select_or_create_cohort,
    select_or_create_contributor,
    upload_cohort_create,
    upload_cohort_edit,
    upload_contributor_create,
    upload_single_accession,
    upload_zip,
)

urlpatterns = [
    path(
        "upload/select-or-create-contributor/",
        select_or_create_contributor,
        name="upload/select-or-create-contributor",
    ),
    path(
        "upload/create-contributor/",
        upload_contributor_create,
        name="upload/create-contributor",
    ),
    path(
        "upload/select-or-create-cohort/<int:contributor_pk>/",
        select_or_create_cohort,
        name="upload/select-or-create-cohort",
    ),
    path(
        "upload/create-cohort/<int:contributor_pk>/",
        upload_cohort_create,
        name="upload/create-cohort",
    ),
    path(
        "upload/edit-cohort/<int:cohort_pk>/",
        upload_cohort_edit,
        name="upload/edit-cohort",
    ),
    path("upload/<int:pk>/files/", cohort_files, name="upload/cohort-files"),
    path(
        "upload/<int:cohort_pk>/upload-single-accession/",
        upload_single_accession,
        name="upload/single-accession",
    ),
    path("upload/<int:cohort_pk>/upload-zip/", upload_zip, name="upload/zip"),
    path(
        "upload/<int:cohort_pk>/upload-metadata/",
        metadata_file_create,
        name="upload/metadata",
    ),
    path("upload/<int:pk>/publish/", cohort_publish, name="upload/cohort-publish"),
    # Staff pages
    path(
        "staff/accession-cog-viewer/<int:pk>/",
        accession_cog_viewer,
        name="ingest/accession-cog-viewer",
    ),
    path("staff/cohorts/", cohort_list, name="ingest/cohort-list"),
    path("staff/merge-cohorts/", cohort_merge, name="ingest/merge-cohorts"),
    path("staff/ingest-review/", ingest_review, name="ingest/ingest-review"),
    path("staff/ingest-review/<int:pk>/", cohort_detail, name="ingest/cohort-detail"),
    path(
        "staff/ingest-review/<int:cohort_pk>/gallery/",
        cohort_review,
        name="ingest/cohort-review",
    ),
    path(
        "staff/ingest-review/<int:cohort_pk>/validate-metadata/",
        apply_metadata,
        name="ingest/validate-metadata",
    ),
    path(
        "staff/ingest-review/metadata-file/<int:metadata_file_pk>/",
        metadata_file_detail,
        name="ingest/metadata-file-detail",
    ),
]
