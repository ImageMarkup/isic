import logging

from django.contrib.auth.models import User
from django.db.models.aggregates import Count

from isic.core.models.collection import Collection

logger = logging.getLogger(__name__)


def collection_create(*, creator: User, name: str, description: str, public: bool):
    return Collection.objects.create(
        creator=creator, name=name, description=description, public=public
    )


def collection_update(collection: Collection, **fields):
    for field, value in fields.items():
        setattr(collection, field, value)

    collection.full_clean()
    return collection.save()


def collection_get_creators_in_attribution_order(*, collection: Collection) -> list[str]:
    """
    Return a list of collection creators in sorted order.

    Creators are ordered by number of images contributed (to this collection), ties are broken
    alphabetically, except for Anonymous contributions which are always last.
    """
    creators = (
        collection.images.alias(num_images=Count('accession__image'))
        .values_list('accession__cohort__attribution', flat=True)
        .order_by('-num_images', 'accession__cohort__attribution')
        .distinct()
    )

    # Push an Anonymous attribution to the end
    creators = sorted(creators, key=lambda x: 1 if x == 'Anonymous' else 0)

    return creators
