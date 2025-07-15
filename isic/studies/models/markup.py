from django.db import models
from django_extensions.db.models import TimeStampedModel
from s3_file_field.fields import S3FileField

from isic.core.storages.utils import generate_upload_to

from .annotation import Annotation
from .feature import Feature


class Markup(TimeStampedModel):
    class Meta:
        unique_together = [["annotation", "feature"]]

    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="markups")
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT, related_name="markups")
    mask = S3FileField(upload_to=generate_upload_to)
    present = models.BooleanField()
