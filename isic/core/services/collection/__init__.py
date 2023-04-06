import logging
from typing import Iterable

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q

from isic.core.models.collection import Collection, CollectionShare
from isic.core.models.doi import Doi
from isic.core.services.collection.image import collection_add_images
from isic.studies.models import Study

logger = logging.getLogger(__name__)


def _require_unlocked_collection(collection: Collection) -> None:
    if Collection.objects.filter(pk=collection.pk, locked=True).exists():
        raise ValidationError("Can't modify the collection, it's locked.")


def collection_create(*, creator: User, name: str, description: str, public: bool, locked: bool):
    collection = Collection(
        creator=creator, name=name, description=description, public=public, locked=locked
    )
    collection.full_clean()
    collection.save()

    return collection


def collection_update(collection: Collection, ignore_lock: bool = False, **fields):
    if not ignore_lock:
        _require_unlocked_collection(collection)

    for field, value in fields.items():
        setattr(collection, field, value)

    collection.full_clean()

    return collection.save()


def collection_lock(*, collection: Collection) -> None:
    if not collection.locked:
        collection_update(collection=collection, locked=True)


def collection_delete(*, collection: Collection, ignore_lock: bool = False) -> None:
    if not ignore_lock:
        _require_unlocked_collection(collection)

    if collection.studies.exists():
        raise ValidationError("Collections with derived studies cannot be deleted.")
    elif collection.has_doi:
        raise ValidationError("Collections with DOIs cannot be deleted.")

    collection.delete()


def collection_get_creators_in_attribution_order(*, collection: Collection) -> list[str]:
    """
    Return a list of collection creators in sorted order.

    Creators are ordered by number of images contributed (to this collection), ties are broken
    alphabetically, except for Anonymous contributions which are always last.
    """
    creators = (
        collection.images.alias(num_images=Count("accession__image"))
        .values_list("accession__cohort__attribution", flat=True)
        .order_by("-num_images", "accession__cohort__attribution")
        .distinct()
    )

    # Push an Anonymous attribution to the end
    creators = sorted(creators, key=lambda x: 1 if x == "Anonymous" else 0)

    return creators


def collection_merge(
    *, dest_collection: Collection, other_collections: Iterable[Collection]
) -> None:
    """
    Merge one or more collections into dest_collection.

    Note that this method should almost always be used with cohort_merge. Merging
    collections or cohorts with relationships to the other would put the system in
    an unexpected state otherwise.
    """
    from_collection_filter = Q(collection=dest_collection) | Q(collection__in=other_collections)

    if Study.objects.filter(from_collection_filter).exists():
        raise ValidationError("Collections with derived studies cannot be merged.")
    elif Doi.objects.filter(from_collection_filter).exists():
        raise ValidationError("Collections with DOIs cannot be merged.")
    elif CollectionShare.objects.filter(from_collection_filter).exists():
        # TODO: This should be allowed, but requires some additional logic
        raise ValidationError("Collections with shares cannot be merged.")

    with transaction.atomic():
        for collection in other_collections:
            # TODO: support dest_collection missing a cohort
            if hasattr(collection, "cohort") and collection.cohort != dest_collection.cohort:
                logger.warning(f"Abandoning cohort {collection.cohort.pk}")

            for field in ["creator", "name", "description", "public", "pinned", "doi", "locked"]:
                dest_collection_value = getattr(dest_collection, field)
                collection_value = getattr(collection, field)
                if dest_collection_value != collection_value:
                    logger.warning(
                        f"Different value for {field}: {dest_collection_value}(dest) vs {collection_value}"  # noqa: E501
                    )

            collection_add_images(
                collection=dest_collection, qs=collection.images.all(), ignore_lock=True
            )
            collection_delete(collection=collection, ignore_lock=True)
