from celery import shared_task
from django.contrib.auth.models import User
from urllib3.exceptions import ConnectionError, TimeoutError

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index
from isic.core.serializers import SearchQueryIn
from isic.core.services.collection.image import collection_add_images


@shared_task(soft_time_limit=600, time_limit=610)
def populate_collection_from_search_task(
    collection_pk: int, user_pk: int, search_params: dict
) -> None:
    user = User.objects.get(pk=user_pk)
    collection = Collection.objects.get(pk=collection_pk)

    if "collections" in search_params and not search_params["collections"]:
        del search_params["collections"]

    serializer = SearchQueryIn(**search_params)
    collection_add_images(collection=collection, qs=serializer.to_queryset(user))


@shared_task(
    soft_time_limit=900,
    time_limit=910,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 15},
)
def sync_elasticsearch_index_task():
    bulk_add_to_search_index(Image.objects.with_elasticsearch_properties().iterator())
