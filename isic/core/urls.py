from django.http.response import Http404
from django.urls import path, register_converter

from isic.core.api import stats as api_stats
from isic.core.constants import ISIC_ID_REGEX, MONGO_ID_REGEX
from isic.core.models.image import Image
from isic.core.models.image_redirect import ImageRedirect
from isic.core.views import collection_detail, collection_list, image_detail, staff_list, stats
from isic.ingest.models.accession import Accession


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

            redirect = ImageRedirect.objects.filter(isic_id=value).first()
            if redirect:
                return redirect.image.pk

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
    path('staff/users/', staff_list, name='core/staff-list'),
    path(
        'staff/collections/',
        collection_list,
        name='core/collection-list',
    ),
    path(
        'staff/collections/<pk>/',
        collection_detail,
        name='core/collection-detail',
    ),
    path(
        'images/<image-identifier:pk>/',
        image_detail,
        name='core/image-detail',
    ),
]
