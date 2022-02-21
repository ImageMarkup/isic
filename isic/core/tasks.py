from celery import shared_task
from django.contrib.auth.models import User

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index
from isic.core.serializers import SearchQuerySerializer


@shared_task
def populate_collection_from_search_task(
    collection_pk: int, user_pk: int, search_params: dict
) -> None:
    user = User.objects.get(pk=user_pk)
    collection = Collection.objects.get(pk=collection_pk)
    serializer = SearchQuerySerializer(data=search_params, context={'user': user})
    serializer.is_valid(raise_exception=True)
    collection.images.add(*serializer.to_queryset())


@shared_task(soft_time_limit=120, time_limit=180)
def sync_elasticsearch_index_task():
    bulk_add_to_search_index(Image.objects.with_elasticsearch_properties().all(), chunk_size=10)
