from django.http.response import Http404
from django.urls import path, register_converter

from isic.core.constants import ISIC_ID_REGEX, MONGO_ID_REGEX
from isic.core.models.image import Image
from isic.core.models.image_alias import ImageAlias
from isic.core.views.collections import (
    collection_create_,
    collection_create_doi_,
    collection_detail,
    collection_download_metadata,
    collection_edit,
    collection_list,
)
from isic.core.views.images import image_browser, image_detail
from isic.core.views.users import staff_list, user_detail
from isic.ingest.models.accession import Accession


class ImageIdentifierConverter:
    regex = f"([0-9]+|{MONGO_ID_REGEX}|{ISIC_ID_REGEX})"

    def to_python(self, value):
        if value.isnumeric():
            return int(value)
        else:
            image = Image.objects.filter(isic_id=value).first()
            if image:
                return image.pk

            image = Image.objects.filter(
                accession=Accession.objects.filter(girder_id=value).first()
            ).first()
            if image:
                return image.pk

            alias = ImageAlias.objects.filter(isic_id=value).first()
            if alias:
                return alias.image.pk

            raise Http404

    def to_url(self, value):
        return int(value)


register_converter(ImageIdentifierConverter, "image-identifier")

urlpatterns = [
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
        "images/<image-identifier:pk>/",
        image_detail,
        name="core/image-detail",
    ),
    path(
        "users/<int:pk>/",
        user_detail,
        name="core/user-detail",
    ),
]
