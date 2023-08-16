from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel
from s3_file_field.fields import S3FileField

from isic.core.constants import MONGO_ID_REGEX
from isic.core.models.image import Image


class Segmentation(TimeStampedModel):
    class Meta:
        ordering = ["id"]

        constraints = [
            models.UniqueConstraint(
                fields=["mask"], condition=~models.Q(mask=""), name="segmentation_unique_mask"
            ),
        ]

    girder_id = models.CharField(
        unique=True,
        max_length=24,
        validators=[RegexValidator(f"^{MONGO_ID_REGEX}$")],
    )
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)
    image = models.ForeignKey(Image, on_delete=models.RESTRICT)
    mask = S3FileField(blank=True)
    meta = models.JSONField(default=dict)


class SegmentationReview(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)
    segmentation = models.ForeignKey(Segmentation, on_delete=models.CASCADE, related_name="reviews")
    approved = models.BooleanField()
    skill = models.CharField(max_length=6, choices=[("novice", "novice"), ("expert", "expert")])
