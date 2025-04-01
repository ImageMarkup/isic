import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q

from isic.core.models.collection import Collection, CollectionShare
from isic.core.models.doi import Doi
from isic.core.services.collection.image import collection_move_images
from isic.core.services.image import image_share
from isic.studies.models import Study

logger = logging.getLogger(__name__)


def _require_unlocked_collection(collection: Collection) -> None:
    if Collection.objects.filter(pk=collection.pk, locked=True).exists():
        raise ValidationError("Can't modify the collection, it's locked.")


def collection_create(*, creator: User, name: str, description: str, public: bool, locked: bool):
    collection = Collection(
        creator=creator,
        name=name,
        description=description,
        public=public,
        locked=locked,
    )
    collection.full_clean()
    collection.save()

    return collection


def collection_update(collection: Collection, *, ignore_lock: bool = False, **fields):
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

    if collection.has_doi:
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
        .values_list("accession__attribution", flat=True)
        .order_by("-num_images", "accession__attribution")
        .distinct()
    )

    # Push an Anonymous attribution to the end
    return sorted(creators, key=lambda x: 1 if x == "Anonymous" else 0)


def collection_share(*, collection: Collection, grantor: User, grantee: User) -> None:
    if collection.is_magic:
        raise ValidationError("Magic collections cannot be shared.")

    # if the collection is public then the images are required to be public, so this method
    # would be a no-op.
    if collection.public:
        return

    with transaction.atomic():
        _, share_created = CollectionShare.objects.get_or_create(
            collection=collection, grantor=grantor, grantee=grantee
        )

        # images only need to be shared if the collection wasn't already shared, since
        # adding images to a shared collection propagates the share to the images.
        if share_created:
            image_share(qs=collection.images.all(), grantor=grantor, grantee=grantee)


def collection_merge_magic_collections(
    *, dest_collection: Collection, src_collection: Collection
) -> None:
    """
    Merge one or more magic collections into a magical dest_collection.

    Note that this method should almost always be used with cohort_merge. Merging
    collections or cohorts with relationships to the other would put the system in
    an unexpected state otherwise.
    """
    from_collection_filter = Q(collection=dest_collection) | Q(collection=src_collection)

    if Study.objects.filter(from_collection_filter).exists():
        raise ValidationError("Collections with derived studies cannot be merged.")
    if Doi.objects.filter(from_collection_filter).exists():
        raise ValidationError("Collections with DOIs cannot be merged.")
    if CollectionShare.objects.filter(from_collection_filter).exists():
        # TODO: This should be allowed, but might require some additional logic. I'm not sure it's
        # clear that merging collection B into A should grant the same shares to A.
        raise ValidationError("Collections with shares cannot be merged.")
    if Collection.objects.filter(id__in=[dest_collection.id, src_collection.id]).regular().exists():
        # Regular means non-magic collections
        raise ValidationError("Regular collections cannot be merged.")

    with transaction.atomic():
        # TODO: support dest_collection missing a cohort
        if hasattr(src_collection, "cohort") and src_collection.cohort != dest_collection.cohort:
            logger.info("Abandoning cohort %s", src_collection.cohort.pk)

        for field in ["public", "pinned", "doi", "locked"]:
            dest_collection_value = getattr(dest_collection, field)
            collection_value = getattr(src_collection, field)
            if dest_collection_value != collection_value:
                logger.warning(
                    "Different value for %s: %s(dest) vs %s",
                    field,
                    dest_collection_value,
                    collection_value,
                )

        collection_move_images(
            src_collection=src_collection,
            dest_collection=dest_collection,
            ignore_lock=True,
        )
        collection_delete(collection=src_collection, ignore_lock=True)
