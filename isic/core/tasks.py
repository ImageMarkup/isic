from celery import shared_task
from django.contrib.auth.models import User

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects


@shared_task
def populate_collection(collection_pk: int, user_pk: int, search_params: dict) -> None:
    user = User.objects.get(pk=user_pk)
    collection = Collection.objects.get(pk=collection_pk)

    images = Image.objects.from_search_query(search_params['query'])

    if search_params.get('collections'):
        images = images.filter(
            collections__in=get_visible_objects(
                user,
                'core.view_collection',
                Collection.objects.filter(pk__in=search_params['collections']),
            )
        )

    collection.images.add(*images)
