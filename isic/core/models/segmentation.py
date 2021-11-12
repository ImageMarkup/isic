from typing import Optional

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django_extensions.db.models import TimeStampedModel
from s3_file_field.fields import S3FileField

from isic.core.constants import MONGO_ID_REGEX
from isic.core.models.image import Image


class Segmentation(TimeStampedModel):
    class Meta:
        ordering = ['id']

    girder_id = models.CharField(
        unique=True,
        max_length=24,
        validators=[RegexValidator(f'^{MONGO_ID_REGEX}$')],
    )
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)
    image = models.ForeignKey(Image, on_delete=models.RESTRICT)
    mask = S3FileField(null=True)
    meta = models.JSONField(default=dict)


class SegmentationReview(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)
    segmentation = models.ForeignKey(Segmentation, on_delete=models.CASCADE, related_name='reviews')
    approved = models.BooleanField()
    skill = models.CharField(max_length=6, choices=[('novice', 'novice'), ('expert', 'expert')])


class SegmentationPermissions:
    model = Segmentation
    perms = ['view_segmentation']
    filters = {'view_segmentation': 'view_segmentation_list'}

    @staticmethod
    def view_segmentation_list(
        user_obj: User, qs: Optional[QuerySet[Segmentation]] = None
    ) -> QuerySet[Segmentation]:
        from isic.core.permissions import get_visible_objects

        qs = qs if qs is not None else Segmentation._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(
                Q(creator=user_obj) | Q(image__in=get_visible_objects(user_obj, 'core.view_image'))
            )
        else:
            return qs.filter(image__in=get_visible_objects(user_obj, 'core.view_image'))

    @staticmethod
    def view_segmentation(user_obj, obj):
        # TODO: use .contains in django 4
        return SegmentationPermissions.view_segmentation_list(user_obj).filter(pk=obj.pk).exists()


Segmentation.perms_class = SegmentationPermissions
