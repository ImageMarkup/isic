from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .base import CopyrightLicense, CreationSortedTimeStampedModel, IsicOAuthApplication
from .collection import Collection
from .doi import Doi
from .girder_image import GirderDataset, GirderImage
from .image import Image
from .image_alias import ImageAlias
from .segmentation import Segmentation, SegmentationReview

__all__ = [
    "Collection",
    "CopyrightLicense",
    "CreationSortedTimeStampedModel",
    "Doi",
    "GirderDataset",
    "GirderImage",
    "Image",
    "ImageAlias",
    "IsicOAuthApplication",
    "Segmentation",
    "SegmentationReview",
]


@receiver(post_save, sender=User)
def add_or_remove_groups(sender: type[User], instance: User, created: bool, **kwargs):
    from django.contrib.auth.models import Group

    if created:
        instance.groups.add(Group.objects.get(name="Public"))
    else:
        isic_staff_group = Group.objects.get(name="ISIC Staff")

        if instance.is_staff:
            instance.groups.add(isic_staff_group)
        else:
            instance.groups.remove(isic_staff_group)
