from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic.base import RedirectView, TemplateView
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions, routers

from isic.core.views import staff_list
from isic.discourse_sso.views import discourse_sso_login
from isic.ingest.api import AccessionViewSet, MetadataFileViewSet
from isic.login.views import IsicLoginView, get_girder_token
from isic.studies.api import AnnotationViewSet, StudyTaskViewSet, StudyViewSet

router = routers.SimpleRouter()
router.register('accessions', AccessionViewSet)
router.register('annotations', AnnotationViewSet)
router.register('metadata-files', MetadataFileViewSet)
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
    path('staff/users/', staff_list, name='staff-list'),
    path('', include('isic.ingest.urls')),
    path('', include('isic.studies.urls')),
]

if apps.is_installed('isic.discourse_sso'):
    urlpatterns += [path('discourse-sso/login/', discourse_sso_login, name='discourse-sso-login')]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
