from celery import shared_task
from django.contrib.auth.models import User

from isic.core.models.collection import Collection
from isic.core.serializers import SearchQuerySerializer


@shared_task
def populate_collection(collection_pk: int, user_pk: int, search_params: dict) -> None:
    user = User.objects.get(pk=user_pk)
    collection = Collection.objects.get(pk=collection_pk)
    serializer = SearchQuerySerializer(data=search_params, context={'user': user})
    serializer.is_valid(raise_exception=True)
    collection.images.add(*serializer.to_queryset())
