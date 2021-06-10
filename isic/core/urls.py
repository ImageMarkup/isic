from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.urls import path, register_converter

from isic.core.api import stats as api_stats
from isic.core.models.image import Image
from isic.core.views import collection_detail, collection_list, image_detail, staff_list, stats


class ImageIdentifierConverter:
    regex = '([0-9]+|[0-9a-f]{24}|ISIC_[0-9]{7})'

    def to_python(self, value):
        if value.isnumeric():
            return int(value)
        else:
            image = get_object_or_404(
                Image.objects.filter(
                    Q(isic_id=value) | Q(accession__girder_id=value) | Q(redirects__isic_id=value)
                ).values('pk')
            )
            return image['pk']

    def to_url(self, value):
        return int(value)


register_converter(ImageIdentifierConverter, 'image-identifier')

urlpatterns = [
    path(
        'images/<image-identifier:pk>/',
        image_detail,
        name='core/image-detail',
    ),
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
    path('staff/users/', staff_list, name='core/staff-list'),
    path(
        'stats/',
        stats,
        name='core/stats',
    ),
    path('api/v2/stats/', api_stats, name='core/api/stats'),
]
