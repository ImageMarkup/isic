from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_yasg2 import openapi
from drf_yasg2.views import get_schema_view
from rest_framework import permissions, routers

from isic.discourse_sso.views import discourse_sso_login
from isic.login.views import IsicLoginView, get_girder_token
from isic.studies.views import *

router = routers.SimpleRouter()
router.register('studies', StudyViewSet)
router.register('annotations', AnnotationViewSet)
router.register('study-tasks', StudyTaskViewSet)

# OpenAPI generation
schema_view = get_schema_view(
    openapi.Info(title='ISIC', default_version='v1', description=''),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('accounts/login/', IsicLoginView.as_view()),
    path('accounts/', include('allauth.urls')),
    path('o/', include('oauth2_provider.urls', namespace='oauth2_provider')),
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api/v1/token/legacy/', get_girder_token),
    path('api/docs/redoc/', schema_view.with_ui('redoc'), name='docs-redoc'),
    path('api/docs/swagger/', schema_view.with_ui('swagger'), name='docs-swagger'),
    path('studies/', StudyListView.as_view()),
    path('studies/<pk>/', StudyDetailView.as_view(), name='study-detail'),
    path('study-annotations/<pk>/', AnnotationDetailView.as_view(), name='study-annotation-detail'),
    path('mask/<markup_id>/', view_mask, name='view-mask'),
]

if apps.is_installed('isic.discourse_sso'):
    urlpatterns += [path('discourse-sso/login/', discourse_sso_login, name='discourse-sso-login')]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path('__debug__/', include(debug_toolbar.urls))] + urlpatterns
