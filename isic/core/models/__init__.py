from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .base import CopyrightLicense, CreationSortedTimeStampedModel, IsicOAuthApplication
from .collection import Collection
from .collection_count import CollectionCount
from .doi import Doi
from .girder_image import GirderDataset, GirderImage
from .image import Image, SimilarImageFeedback
from .image_alias import ImageAlias
from .isic_id import IsicId
from .segmentation import Segmentation, SegmentationReview
from .supplemental_file import SupplementalFile

__all__ = [
    "Collection",
    "CollectionCount",
    "CopyrightLicense",
    "CreationSortedTimeStampedModel",
    "Doi",
    "GirderDataset",
    "GirderImage",
    "Image",
    "ImageAlias",
    "IsicId",
    "IsicOAuthApplication",
    "Segmentation",
    "SegmentationReview",
    "SimilarImageFeedback",
    "SupplementalFile",
]


@receiver(post_save, sender=User)
def add_or_remove_groups(
    sender: type[User],
    instance: User,
    created: bool,  # noqa: FBT001
    **kwargs,
):
    from django.contrib.auth.models import Group

    if created:
        instance.groups.add(Group.objects.get(name="Public"))
    else:
        isic_staff_group = Group.objects.get(name="ISIC Staff")

        if instance.is_staff:
            instance.groups.add(isic_staff_group)
        else:
            instance.groups.remove(isic_staff_group)
