from django.http.response import Http404
from django.urls import path, register_converter

from isic.core.api import stats as api_stats, user_me
from isic.core.constants import ISIC_ID_REGEX, MONGO_ID_REGEX
from isic.core.models.image import Image
from isic.core.models.image_alias import ImageAlias
from isic.core.views import (
    collection_create_doi,
    collection_detail,
    collection_list,
    image_browser,
    image_detail,
    staff_list,
    stats,
)
from isic.ingest.models.accession import Accession
from isic.login.views import accept_terms_of_use


class ImageIdentifierConverter:
    regex = f'([0-9]+|{MONGO_ID_REGEX}|{ISIC_ID_REGEX})'

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


register_converter(ImageIdentifierConverter, 'image-identifier')

urlpatterns = [
    path(
        'stats/',
        stats,
        name='core/stats',
    ),
    path('api/v2/stats/', api_stats, name='core/api/stats'),
    path('api/v2/users/me/', user_me, name='core/api/users/me'),
    path('api/v2/users/accept-terms/', accept_terms_of_use, name='core/api/users/accept-terms'),
    path('staff/users/', staff_list, name='core/staff-list'),
    path(
        'images/',
        image_browser,
        name='core/image-browser',
    ),
    path(
        'collections/',
        collection_list,
        name='core/collection-list',
    ),
    path(
        'collections/<int:pk>/',
        collection_detail,
        name='core/collection-detail',
    ),
    path(
        'collections/<int:pk>/create-doi/',
        collection_create_doi,
        name='core/collection-create-doi',
    ),
    path(
        'images/<image-identifier:pk>/',
        image_detail,
        name='core/image-detail',
    ),
]
