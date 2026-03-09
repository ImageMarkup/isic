from django.conf import settings
from django.core.files.storage import storages
from django.shortcuts import render


def data_explorer(request):
    storage = storages["sponsored"]
    return render(
        request,
        "core/data_explorer.html",
        {
            "parquet_url": storage.unsigned_url(settings.ISIC_DATA_EXPLORER_PARQUET_KEY),
            "thumbnail_base_url": storage.unsigned_url("thumbnails/"),
        },
    )
