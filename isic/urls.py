from functools import partial

from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.urls import include, path, reverse_lazy
from django.views.generic.base import RedirectView
from ninja import NinjaAPI
from ninja.openapi.views import openapi_view

from isic.auth import allow_any
from isic.core.api.collection import router as collection_router
from isic.core.api.doi import router as doi_router
from isic.core.api.image import ImageSearchParseError
from isic.core.api.image import router as image_router
from isic.core.api.user import router as user_router
from isic.core.sitemaps import sitemaps
from isic.find.api import autocomplete_router
from isic.find.api import router as quickfind_router
from isic.ingest.api import (
    accession_router,
    cohort_router,
    contributor_router,
    lesion_router,
    metadata_file_router,
)
from isic.stats.api import stats_router
from isic.studies.api import annotation_router, study_router, study_task_router
from isic.zip_download.api import zip_router

api = NinjaAPI(
    title="ISIC Archive",
    description=render_to_string("core/swagger_description.html"),
    version="v2",
    docs_url=None,  # we want to serve the docs next to the ninja root rather than under it
    auth=allow_any,
    csrf=True,
    urls_namespace="api",
)
swagger_view = partial(openapi_view, api=api)

api.add_router("/accessions/", accession_router, tags=["accessions"])
api.add_router("/annotations/", annotation_router, tags=["annotations"])
api.add_router("/autocomplete/", autocomplete_router, tags=["autocomplete"])
api.add_router("/cohorts/", cohort_router, tags=["cohorts"])
api.add_router("/collections/", collection_router, tags=["collections"])
api.add_router("/contributors/", contributor_router, tags=["contributors"])
api.add_router("/doi/", doi_router, tags=["doi"])
api.add_router("/images/", image_router, tags=["images"])
api.add_router("/lesions/", lesion_router, tags=["lesions"])
api.add_router("/metadata-files/", metadata_file_router, tags=["metadata-files"])
api.add_router("/quickfind/", quickfind_router, tags=["quickfind"])
api.add_router("/stats/", stats_router, tags=["stats"])
api.add_router("/studies/", study_router, tags=["studies"])
api.add_router("/study-tasks/", study_task_router, tags=["study-tasks"])
api.add_router("/users/", user_router, tags=["users"])
api.add_router("/zip-download/", zip_router, tags=["zip-downloads"])


@api.exception_handler(ValidationError)
def handle_django_validation_error(request, exc: ValidationError):
    return api.create_response(
        request,
        {"message": exc.message},
        status=400,
    )


@api.exception_handler(ImageSearchParseError)
def handle_image_search_parse_error(request, exc: ImageSearchParseError):
    return api.create_response(
        request,
        {"message": "Could not parse search query."},
        status=400,
    )


urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("oauth/", include("oauth2_provider.urls")),
    path("admin/", admin.site.urls),
    path("api/v2/s3-upload/", include("s3_file_field.urls")),
    path("api/v2/", api.urls),
    path("api/docs/swagger/", swagger_view, name="docs-swagger"),
    path(
        "sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"
    ),
    # Core app
    path("", RedirectView.as_view(url=reverse_lazy("core/image-browser")), name="index"),
    path("", include("isic.core.urls")),
    path("", include("isic.ingest.urls")),
    path("", include("isic.stats.urls")),
    path("", include("isic.studies.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls)), *urlpatterns]
