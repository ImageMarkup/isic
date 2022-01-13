from django.urls import path

from isic.ingest import views
import isic.ingest.views.metadata as metadata_views
import isic.ingest.views.review_apps as review_apps_views
import isic.ingest.views.upload as upload_views

urlpatterns = [
    path(
        'upload/select-or-create-contributor/',
        upload_views.select_or_create_contributor,
        name='upload/select-or-create-contributor',
    ),
    path(
        'upload/create-contributor/',
        upload_views.upload_contributor_create,
        name='upload/create-contributor',
    ),
    path(
        'upload/select-or-create-cohort/<int:contributor_pk>/',
        upload_views.select_or_create_cohort,
        name='upload/select-or-create-cohort',
    ),
    path(
        'upload/create-cohort/<int:contributor_pk>',
        upload_views.upload_cohort_create,
        name='upload/create-cohort',
    ),
    path('upload/<int:pk>/files/', upload_views.cohort_files, name='upload/cohort-files'),
    path(
        'upload/<int:cohort_pk>/upload-single-accession/',
        views.upload_single_accession,
        name='upload/single-accession',
    ),
    path('upload/<int:cohort_pk>/upload-zip/', views.upload_zip, name='upload/zip'),
    path(
        'upload/<int:cohort_pk>/upload-metadata/',
        metadata_views.metadata_file_create,
        name='upload-metadata',
    ),
    path('upload/<int:pk>/browser/', views.cohort_browser, name='upload/cohort-browser'),
    path('upload/<int:pk>/publish/', views.publish_cohort, name='upload/cohort-publish'),
    # Staff pages
    path('staff/ingest-review/', views.ingest_review, name='ingest-review'),
    path('staff/ingest-review/<int:pk>/', views.cohort_detail, name='cohort-detail'),
    path(
        'staff/ingest-review/diagnosis/<int:cohort_pk>/',
        review_apps_views.DiagnosisReviewAppView.as_view(),
        name='cohort-review-diagnosis',
    ),
    path(
        'staff/ingest-review/quality-and-phi/<int:cohort_pk>/',
        review_apps_views.QualityPhiReviewAppView.as_view(),
        name='cohort-review-quality-and-phi',
    ),
    path(
        'staff/ingest-review/duplicate/<int:cohort_pk>/',
        review_apps_views.DuplicateReviewAppView.as_view(),
        name='cohort-review-duplicate',
    ),
    path(
        'staff/ingest-review/lesion/<int:cohort_pk>/',
        review_apps_views.lesion_review,
        name='cohort-review-lesion',
    ),
    path(
        'staff/ingest-review/<int:cohort_pk>/validate-metadata/',
        metadata_views.apply_metadata,
        name='validate-metadata',
    ),
    path(
        'staff/reset-metadata/<int:cohort_pk>/',
        metadata_views.reset_metadata,
        name='reset-metadata',
    ),
]
