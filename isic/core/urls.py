from django.urls import path

from isic.core.views import collection_detail, collection_list, image_detail, stats

urlpatterns = [
    path(
        'images/<id_or_gid_or_isicid>/',
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
    path(
        'stats/',
        stats,
        name='core/stats',
    ),
]
