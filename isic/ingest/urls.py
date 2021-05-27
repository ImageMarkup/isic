from django.urls import path

from isic.ingest.views import (
    DiagnosisReviewAppView,
    DuplicateReviewAppView,
    LesionReviewAppView,
    QualityPhiReviewAppView,
    apply_metadata,
    cohort_detail,
    cohort_files,
    cohort_list,
    ingest_review,
    metadata_file_create,
    reset_metadata,
    select_or_create_cohort,
    select_or_create_contributor,
    upload_cohort_create,
    upload_contributor_create,
    zip_create,
)

urlpatterns = [
    path(
        'upload/select-or-create-contributor/',
        select_or_create_contributor,
        name='upload/select-or-create-contributor',
    ),
    path('upload/create-contributor/', upload_contributor_create, name='upload/create-contributor'),
    path(
        'upload/select-or-create-cohort/<contributor_pk>/',
        select_or_create_cohort,
        name='upload/select-or-create-cohort',
    ),
    path(
        'upload/create-cohort/<contributor_pk>', upload_cohort_create, name='upload/create-cohort'
    ),
    path('upload/<pk>/files/', cohort_files, name='upload/cohort-files'),
    path('upload/<cohort_pk>/upload-zip/', zip_create, name='upload-zip'),
    path('upload/<cohort_pk>/upload-metadata/', metadata_file_create, name='upload-metadata'),
    # Staff pages
    path('staff/ingest-review/', ingest_review, name='ingest-review'),
    path('staff/cohorts/', cohort_list, name='cohort-list'),
    path('staff/ingest-review/<pk>/', cohort_detail, name='cohort-detail'),
    path(
        'staff/ingest-review/diagnosis/<cohort_pk>/',
        DiagnosisReviewAppView.as_view(),
        name='cohort-review-diagnosis',
    ),
    path(
        'staff/ingest-review/quality-and-phi/<cohort_pk>/',
        QualityPhiReviewAppView.as_view(),
        name='cohort-review-quality-and-phi',
    ),
    path(
        'staff/ingest-review/duplicate/<cohort_pk>/',
        DuplicateReviewAppView.as_view(),
        name='cohort-review-duplicate',
    ),
    path(
        'staff/ingest-review/lesion/<cohort_pk>/',
        LesionReviewAppView.as_view(),
        name='cohort-review-lesion',
    ),
    path(
        'staff/ingest-review/<cohort_pk>/validate-metadata/',
        apply_metadata,
        name='validate-metadata',
    ),
    path('staff/reset-metadata/<cohort_pk>/', reset_metadata, name='reset-metadata'),
]
