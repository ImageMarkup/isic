import itertools

from cachalot.api import cachalot_disabled
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query import QuerySet

from isic.core.models.collection import Collection, CollectionShare
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.core.services.image import image_share


def collection_add_images(
    *,
    collection: Collection,
    qs: QuerySet[Image] | None = None,
    image: Image | None = None,
    ignore_lock: bool = False,
):
    # is not None is necessary because qs could be an empty queryset
    if qs is not None and image is not None:
        raise ValueError("qs and image are mutually exclusive arguments.")

    if image:
        qs = Image.objects.filter(pk=image.pk)

    if collection.locked and not ignore_lock:
        raise ValidationError("Can't add images to locked collection.")

    if collection.public and qs.private().exists():  # type: ignore[union-attr]
        raise ValidationError("Can't add private images to a public collection.")

    with transaction.atomic(), cachalot_disabled():
        CollectionImageM2M = Collection.images.through  # noqa: N806
        for image_batch in itertools.batched(qs.iterator(), 5_000):  # type: ignore[union-attr]
            # ignore_conflicts is necessary to make this method idempotent (consistent with
            # collection.images.add) ignore_conflicts only ignores primary key, duplicate, and
            # exclusion constraints. we don't use primary key or exclusion here, so this should
            # only ignore duplicate entries.
            CollectionImageM2M.objects.bulk_create(
                [CollectionImageM2M(collection=collection, image=image) for image in image_batch],
                ignore_conflicts=True,
            )

        # adding images to a collection that's shared with a user should implicitly share the
        # images with that user.
        for collection_share in CollectionShare.objects.filter(collection=collection).all():
            image_share(qs=qs, grantor=collection_share.grantor, grantee=collection_share.grantee)


def collection_move_images(
    *,
    src_collection: Collection,
    dest_collection: Collection,
    ignore_lock: bool = False,
):
    """
    Move images from one collection to another.

    This is effectively the same as removing images from one collection and adding them to
    another, but it's more efficient and does all of the correct safety checks.
    """
    if not ignore_lock and (src_collection.locked or dest_collection.locked):
        raise ValidationError("Can't move images to/from a locked collection.")

    if dest_collection.public and src_collection.images.private().exists():  # type: ignore[attr-defined]
        raise ValidationError("Can't move private images to a public collection.")

    with transaction.atomic():
        CollectionImageM2M = Collection.images.through  # noqa: N806

        # first remove the images from the source collection that are already in the
        # destination collection to avoid unique constraint violations.
        CollectionImageM2M.objects.filter(
            collection=src_collection, image__in=dest_collection.images.all()
        ).delete()

        # migrate the remaining images to point to the destination collection
        CollectionImageM2M.objects.filter(
            collection=src_collection, image__in=src_collection.images.all()
        ).exclude(image__in=dest_collection.images.all()).update(collection=dest_collection)


def collection_remove_images(
    *,
    collection: Collection,
    qs: QuerySet[Image] | None = None,
    image: Image | None = None,
    ignore_lock: bool = False,
):
    # is not None is necessary because qs could be an empty queryset
    if qs is not None and image is not None:
        raise ValueError("qs and image are mutually exclusive arguments.")

    if image:
        qs = Image.objects.filter(pk=image.pk)

    if collection.locked and not ignore_lock:
        raise ValidationError("Can't remove images from a locked collection.")

    Collection.images.through.objects.filter(collection=collection, image__in=qs).delete()


def collection_add_images_from_isic_ids(
    *, user: User, collection: Collection, isic_ids: list[str]
) -> dict:
    isic_ids = list(set(isic_ids))
    visible_images = get_visible_objects(
        user, "core.view_image", Image.objects.filter(isic_id__in=isic_ids)
    ).in_bulk(field_name="isic_id")

    no_perms_or_does_not_exist = [isic_id for isic_id in isic_ids if isic_id not in visible_images]
    private_image_public_collection = [
        isic_id
        for isic_id in isic_ids
        if collection.public and isic_id in visible_images and not visible_images[isic_id].public
    ]
    succeeded = list(
        set(isic_ids) - set(no_perms_or_does_not_exist) - set(private_image_public_collection)
    )
    summary = {
        "no_perms_or_does_not_exist": no_perms_or_does_not_exist,
        "private_image_public_collection": private_image_public_collection,
        "succeeded": succeeded,
    }

    collection_add_images(
        collection=collection, qs=Image.objects.filter(isic_id__in=summary["succeeded"])
    )

    return summary


def collection_remove_images_from_isic_ids(
    *, user: User, collection: Collection, isic_ids: list[str]
) -> dict:
    isic_ids = list(set(isic_ids))
    visible_images = get_visible_objects(
        user, "core.view_image", Image.objects.filter(isic_id__in=isic_ids)
    ).in_bulk(field_name="isic_id")

    summary = {
        "no_perms_or_does_not_exist": [
            isic_id for isic_id in isic_ids if isic_id not in visible_images
        ],
        "succeeded": [isic_id for isic_id in isic_ids if isic_id in visible_images],
    }

    collection_remove_images(
        collection=collection, qs=Image.objects.filter(isic_id__in=summary["succeeded"])
    )

    return summary
