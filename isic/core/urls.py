from django.urls import path
from django.views.generic.base import TemplateView

from isic.core.views.collections import (
    collection_create_,
    collection_create_doi_,
    collection_detail,
    collection_download_metadata,
    collection_edit,
    collection_list,
)
from isic.core.views.doi import doi_detail, draft_doi_edit
from isic.core.views.embargoed import embargoed_dashboard
from isic.core.views.images import (
    image_browser,
    image_detail,
    staff_image_list_export,
    staff_image_list_metadata_download,
)
from isic.core.views.lesion import lesion_detail
from isic.core.views.users import staff_list, user_detail

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="core/robots.txt", content_type="text/plain"),
    ),
    path("staff/users/", staff_list, name="core/staff-list"),
    path("staff/embargoed-dashboard/", embargoed_dashboard, name="core/embargoed-dashboard"),
    path(
        "images/",
        image_browser,
        name="core/image-browser",
    ),
    path(
        "collections/",
        collection_list,
        name="core/collection-list",
    ),
    path(
        "collections/<int:pk>/",
        collection_detail,
        name="core/collection-detail",
    ),
    path(
        "collections/create/",
        collection_create_,
        name="core/collection-create",
    ),
    path(
        "collections/edit/<int:pk>/",
        collection_edit,
        name="core/collection-edit",
    ),
    path(
        "collections/<int:pk>/create-doi/",
        collection_create_doi_,
        name="core/collection-create-doi",
    ),
    path(
        "collections/<int:pk>/metadata/",
        collection_download_metadata,
        name="core/collection-download-metadata",
    ),
    path(
        "images/<str:image_identifier>/",
        image_detail,
        name="core/image-detail",
    ),
    path(
        "lesions/<str:identifier>/",
        lesion_detail,
        name="core/lesion-detail",
    ),
    path(
        "users/<int:pk>/",
        user_detail,
        name="core/user-detail",
    ),
    path("staff/image-list/", staff_image_list_export, name="core/image-list-export"),
    path(
        "staff/image-list/metadata-download/",
        staff_image_list_metadata_download,
        name="core/image-list-metadata-download",
    ),
    path("doi/<slug:slug>/", doi_detail, name="core/doi-detail"),
    path("doi/<slug:slug>/edit/", draft_doi_edit, name="core/draft-doi-edit"),
]
