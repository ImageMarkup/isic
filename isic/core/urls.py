from django.urls import path

from isic.core.views import collection_detail, image_detail

urlpatterns = [
    path(
        'images/<id_or_gid_or_isicid>/',
        image_detail,
        name='core/image-detail',
    ),
    path(
        'collections/<pk>/',
        collection_detail,
        name='core/collection-detail',
    ),
]
