from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects


def collection_add_images(
    *,
    collection: Collection,
    qs: QuerySet[Image] = None,
    image: Image = None,
    ignore_lock: bool = False,
):
    assert qs or image, 'qs and image are mutually exclusive arguments.'

    if image:
        qs = Image.objects.filter(pk=image.pk)

    if collection.locked and not ignore_lock:
        raise ValidationError("Can't add images to locked collection.")

    if collection.public and qs.filter(public=False).exists():
        raise ValidationError("Can't add private images to a public collection.")

    collection.images.add(*qs)


def collection_remove_images(
    *,
    collection: Collection,
    qs: QuerySet[Image] = None,
    image: Image = None,
    ignore_lock: bool = False,
):
    assert qs or image, 'qs and image are mutually exclusive arguments.'

    if image:
        qs = Image.objects.filter(pk=image.pk)

    if collection.locked and not ignore_lock:
        raise ValidationError("Can't remove images from a locked collection.")

    collection.images.remove(*qs)


def collection_add_images_from_isic_ids(
    *, user: User, collection: Collection, isic_ids: list[str]
) -> dict:
    isic_ids = list(set(isic_ids))
    visible_images = get_visible_objects(
        user, 'core.view_image', Image.objects.filter(isic_id__in=isic_ids)
    ).in_bulk(field_name='isic_id')

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
        'no_perms_or_does_not_exist': no_perms_or_does_not_exist,
        'private_image_public_collection': private_image_public_collection,
        'succeeded': succeeded,
    }

    collection_add_images(
        collection=collection, qs=Image.objects.filter(isic_id__in=summary['succeeded'])
    )

    return summary


def collection_remove_images_from_isic_ids(
    *, user: User, collection: Collection, isic_ids: list[str]
) -> dict:
    isic_ids = list(set(isic_ids))
    visible_images = get_visible_objects(
        user, 'core.view_image', Image.objects.filter(isic_id__in=isic_ids)
    ).in_bulk(field_name='isic_id')

    summary = {
        'no_perms_or_does_not_exist': [
            isic_id for isic_id in isic_ids if isic_id not in visible_images
        ],
        'succeeded': [isic_id for isic_id in isic_ids if isic_id in visible_images],
    }

    collection_remove_images(
        collection=collection, qs=Image.objects.filter(isic_id__in=summary['succeeded'])
    )

    return summary
