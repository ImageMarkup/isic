from django.conf import settings
from django.contrib import admin
from django.template.loader import render_to_string
from django.urls import include, path, reverse_lazy
from django.views.generic.base import RedirectView
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework import permissions, routers

from isic.core.api import CollectionViewSet, ImageViewSet
from isic.ingest.api import CohortViewSet, ContributorViewSet, MetadataFileViewSet
from isic.studies.api import AnnotationViewSet, StudyTaskViewSet, StudyViewSet

router = routers.SimpleRouter()
router.register('annotations', AnnotationViewSet)
router.register('cohorts', CohortViewSet)
router.register('collections', CollectionViewSet)
router.register('contributors', ContributorViewSet)
router.register('images', ImageViewSet)
router.register('metadata-files', MetadataFileViewSet)
router.register('studies', StudyViewSet)
router.register('study-tasks', StudyTaskViewSet)


# TODO: Removed this once https://github.com/girder/django-s3-file-field/issues/257 is resolved.
class ExcludeS3FFGenerator(OpenAPISchemaGenerator):
    def should_include_endpoint(self, path, method, view, public):
        return 's3-upload' not in path


# OpenAPI generation
schema_view = get_schema_view(
    openapi.Info(
        title='ISIC Archive',
        default_version='v2',
        description=render_to_string('core/swagger_description.html'),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    generator_class=ExcludeS3FFGenerator,
)

urlpatterns = [
    path('accounts/', include('allauth.urls')),
    path('oauth/', include('oauth2_provider.urls')),
    path('admin/', admin.site.urls),
    path('api/v2/s3-upload/', include('s3_file_field.urls')),
    path('api/v2/', include(router.urls)),
    path('api/docs/redoc/', schema_view.with_ui('redoc'), name='docs-redoc'),
    path('api/docs/swagger/', schema_view.with_ui('swagger'), name='docs-swagger'),
    # Core app
    path('', RedirectView.as_view(url=reverse_lazy('core/image-browser')), name='index'),
    path('', include('isic.core.urls')),
    path('', include('isic.find.urls')),
    path('', include('isic.ingest.urls')),
    path('', include('isic.stats.urls')),
    path('', include('isic.studies.urls')),
    path('', include('isic.zip_download.urls')),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
