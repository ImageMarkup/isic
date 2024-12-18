from django.db.models import Q
from django.http.response import Http404
from django.urls import path, register_converter
from django.views.generic.base import TemplateView

from isic.core.constants import ISIC_ID_REGEX, MONGO_ID_REGEX
from isic.core.models.image import Image
from isic.core.views.collections import (
    collection_create_,
    collection_create_doi_,
    collection_detail,
    collection_download_metadata,
    collection_edit,
    collection_list,
)
from isic.core.views.images import (
    image_browser,
    image_detail,
    staff_image_list_export,
    staff_image_list_metadata_download,
)
from isic.core.views.lesion import lesion_detail
from isic.core.views.users import staff_list, user_detail


class ImageIdentifierConverter:
    regex = f"([0-9]+|{MONGO_ID_REGEX}|{ISIC_ID_REGEX})"

    def to_python(self, value):
        if value.isnumeric():
            image = Image.objects.filter(pk=value).first()
            if image:
                return image.isic_id
        else:
            for approach in [
                Q(isic_id=value),
                Q(accession__girder_id=value),
                Q(aliases__isic=value),
            ]:
                image = Image.objects.filter(approach).order_by().first()
                if image:
                    return image.isic_id

        raise Http404

    def to_url(self, value):
        return value


register_converter(ImageIdentifierConverter, "image-identifier")

urlpatterns = [
    path(
        "robots.txt",
        TemplateView.as_view(template_name="core/robots.txt", content_type="text/plain"),
    ),
    path("staff/users/", staff_list, name="core/staff-list"),
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
        "images/<image-identifier:isic_id>/",
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
]
