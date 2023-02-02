from django.urls import include, path

from isic.ingest.api import AccessionCreateApi, AccessionCreateReviewBulkApi
import isic.ingest.views.cohort as cohort_views
import isic.ingest.views.metadata as metadata_views
import isic.ingest.views.review as review_views
import isic.ingest.views.upload as upload_views

accession_api_patterns = [
    path("", AccessionCreateApi.as_view(), name="create"),
    path("create-review-bulk/", AccessionCreateReviewBulkApi.as_view(), name="create-review-bulk"),
]


urlpatterns = [
    path("api/v2/accessions/", include((accession_api_patterns, "accessions"))),
    path(
        "upload/select-or-create-contributor/",
        upload_views.select_or_create_contributor,
        name="upload/select-or-create-contributor",
    ),
    path(
        "upload/create-contributor/",
        upload_views.upload_contributor_create,
        name="upload/create-contributor",
    ),
    path(
        "upload/select-or-create-cohort/<int:contributor_pk>/",
        upload_views.select_or_create_cohort,
        name="upload/select-or-create-cohort",
    ),
    path(
        "upload/create-cohort/<int:contributor_pk>",
        upload_views.upload_cohort_create,
        name="upload/create-cohort",
    ),
    path(
        "upload/edit-cohort/<int:cohort_pk>",
        upload_views.upload_cohort_edit,
        name="upload/edit-cohort",
    ),
    path("upload/<int:pk>/files/", upload_views.cohort_files, name="upload/cohort-files"),
    path(
        "upload/<int:cohort_pk>/upload-single-accession/",
        upload_views.upload_single_accession,
        name="upload/single-accession",
    ),
    path("upload/<int:cohort_pk>/upload-zip/", upload_views.upload_zip, name="upload/zip"),
    path(
        "upload/<int:cohort_pk>/upload-metadata/",
        metadata_views.metadata_file_create,
        name="upload-metadata",
    ),
    path("upload/<int:pk>/publish/", cohort_views.publish_cohort, name="upload/cohort-publish"),
    # Staff pages
    path("staff/cohorts/", cohort_views.cohort_list, name="cohort-list"),
    path("staff/ingest-review/", review_views.ingest_review, name="ingest-review"),
    path("staff/ingest-review/<int:pk>/", cohort_views.cohort_detail, name="cohort-detail"),
    path(
        "staff/ingest-review/<int:cohort_pk>/gallery/",
        review_views.cohort_review,
        name="cohort-review",
    ),
    path(
        "staff/ingest-review/<int:cohort_pk>/validate-metadata/",
        metadata_views.apply_metadata,
        name="validate-metadata",
    ),
]
