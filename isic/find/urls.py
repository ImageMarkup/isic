from django.urls import path

from isic.find.api import quickfind

urlpatterns = [
    path(
        'api/v2/quickfind/',
        quickfind,
        name='find/api/quickfind',
    ),
]
