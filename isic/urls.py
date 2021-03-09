from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic.base import RedirectView, TemplateView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions, routers

from isic.discourse_sso.views import discourse_sso_login
from isic.ingest.api import AccessionViewSet
from isic.ingest.review_views import (
    DiagnosisReviewAppView,
    DuplicateReviewAppView,
    LesionReviewAppView,
    QualityPhiReviewAppView,
)
from isic.ingest.views import (
    apply_metadata,
    cohort_detail,
    cohort_files,
    cohort_list,
    reset_metadata,
    review_skipped_accessions,
    upload_cohort_create,
    upload_contributor_create,
    zip_create,
)
from isic.login.views import IsicLoginView, get_girder_token
from isic.studies.api import AnnotationViewSet, StudyTaskViewSet, StudyViewSet
from isic.studies.views import annotation_detail, study_create, study_detail, study_list, view_mask

router = routers.SimpleRouter()
router.register('accessions', AccessionViewSet)
router.register('annotations', AnnotationViewSet)
router.register('studies', StudyViewSet)
router.register('study-tasks', StudyTaskViewSet)

# OpenAPI generation
schema_view = get_schema_view(
    openapi.Info(title='ISIC', default_version='v2', description=''),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('accounts/login/', IsicLoginView.as_view()),
    path('accounts/', include('allauth.urls')),
    path('oauth/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('admin/', admin.site.urls),
    path('api/v2/s3-upload/', include('s3_file_field.urls')),
    path('api/v2/token/legacy/', get_girder_token),
    path('api/v2/', include(router.urls)),
    path('api/docs/redoc/', schema_view.with_ui('redoc'), name='docs-redoc'),
    path('api/docs/swagger/', schema_view.with_ui('swagger'), name='docs-swagger'),
    # Core app
    path('', RedirectView.as_view(url=reverse_lazy('staff-index')), name='index'),
    path(
        'staff/', TemplateView.as_view(template_name='core/staff_landing.html'), name='staff-index'
    ),
    # Studies app
    path('staff/studies/create/', study_create, name='study-create'),
    path('staff/studies/', study_list, name='study-list'),
    path('staff/studies/<pk>/', study_detail, name='study-detail'),
    path('staff/masks/<markup_id>/', view_mask, name='view-mask'),
    path('staff/annotations/<pk>/', annotation_detail, name='annotation-detail'),
    # Ingest app
    path('upload/create-contributor/', upload_contributor_create, name='contributor-create'),
    path('upload/create-cohort/<contributor_pk>', upload_cohort_create, name='cohort-create'),
    path('cohort/<pk>/', cohort_detail, name='cohort-detail'),
    path('cohort/<pk>/files', cohort_files, name='cohort-files'),
    # Staff pges
    path('staff/upload/create/<cohort_pk>/', zip_create, name='zip-create'),
    path('staff/cohorts/', cohort_list, name='cohort-list'),
    path('staff/cohort/<pk>/', cohort_detail, name='cohort-detail'),
    path(
        'staff/review/diagnosis/<cohort_pk>/',
        DiagnosisReviewAppView.as_view(),
        name='cohort-review-diagnosis',
    ),
    path(
        'staff/review/quality-and-phi/<cohort_pk>/',
        QualityPhiReviewAppView.as_view(),
        name='cohort-review-quality-and-phi',
    ),
    path(
        'staff/review/duplicate/<cohort_pk>/',
        DuplicateReviewAppView.as_view(),
        name='cohort-review-duplicate',
    ),
    path(
        'staff/review/lesion/<cohort_pk>/',
        LesionReviewAppView.as_view(),
        name='cohort-review-lesion',
    ),
    path(
        'staff/review-skipped-accessions/<cohort_pk>/',
        review_skipped_accessions,
        name='review-skipped-accessions',
    ),
    path('staff/apply-metadata/<cohort_pk>/', apply_metadata, name='apply-metadata'),
    path('staff/reset-metadata/<cohort_pk>/', reset_metadata, name='reset-metadata'),
]

if apps.is_installed('isic.discourse_sso'):
    urlpatterns += [path('discourse-sso/login/', discourse_sso_login, name='discourse-sso-login')]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
