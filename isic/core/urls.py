from django.urls import path

from isic.core.views import image_detail

urlpatterns = [
    path(
        'images/<id_or_gid_or_isicid>/',
        image_detail,
        name='core/image-detail',
    ),
]
