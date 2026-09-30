from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import URLPattern, URLResolver, include, path, reverse_lazy
from django.views.generic.base import RedirectView

from isic.core.api.collection import urlpatterns as collection_urlpatterns
from isic.core.api.docs import openapi_schema, swagger
from isic.core.api.doi import urlpatterns as doi_urlpatterns
from isic.core.api.image import urlpatterns as image_urlpatterns
from isic.core.api.user import urlpatterns as user_urlpatterns
from isic.core.sitemaps import sitemaps
from isic.engagement.api import urlpatterns as engagement_urlpatterns
from isic.find.api import autocomplete_urlpatterns, quickfind_urlpatterns
from isic.ingest.api import (
    accession_urlpatterns,
    cohort_urlpatterns,
    contributor_urlpatterns,
    lesion_urlpatterns,
    metadata_file_urlpatterns,
)
from isic.stats.api import urlpatterns as stats_urlpatterns
from isic.studies.api import (
    annotation_urlpatterns,
    study_task_urlpatterns,
    study_urlpatterns,
)
from isic.zip_download.api import urlpatterns as zip_download_urlpatterns

api_urlpatterns: list[URLPattern | URLResolver] = [
    path("accessions/", include(accession_urlpatterns)),
    path("annotations/", include(annotation_urlpatterns)),
    path("autocomplete/", include(autocomplete_urlpatterns)),
    path("cohorts/", include(cohort_urlpatterns)),
    path("collections/", include(collection_urlpatterns)),
    path("contributors/", include(contributor_urlpatterns)),
    path("doi/", include(doi_urlpatterns)),
    path("engagement/", include(engagement_urlpatterns)),
    path("images/", include(image_urlpatterns)),
    path("lesions/", include(lesion_urlpatterns)),
    path("metadata-files/", include(metadata_file_urlpatterns)),
    path("quickfind/", include(quickfind_urlpatterns)),
    path("stats/", include(stats_urlpatterns)),
    path("studies/", include(study_urlpatterns)),
    path("study-tasks/", include(study_task_urlpatterns)),
    path("users/", include(user_urlpatterns)),
    path("zip-download/", include(zip_download_urlpatterns)),
    path("openapi.json", openapi_schema, name="openapi-json"),
]

urlpatterns = [
    path("accounts/", include("allauth.urls")),
    path("oauth/", include("oauth2_provider.urls")),
    path("admin/", admin.site.urls),
    path("api/v2/s3-upload/", include("s3_file_field.urls")),
    path("api/v2/", include((api_urlpatterns, "api"))),
    path("api/docs/swagger/", swagger, name="docs-swagger"),
    path(
        "sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"
    ),
    # Core app
    path("", RedirectView.as_view(url=reverse_lazy("core/image-browser")), name="index"),
    path("", include("isic.core.urls")),
    path("", include("isic.engagement.urls")),
    path("", include("isic.ingest.urls")),
    path("", include("isic.login.urls")),
    path("", include("isic.stats.urls")),
    path("", include("isic.studies.urls")),
]


if settings.DEBUG:
    import debug_toolbar.toolbar

    urlpatterns += [
        *debug_toolbar.toolbar.debug_toolbar_urls(),
        path("__reload__/", include("django_browser_reload.urls")),
    ]
