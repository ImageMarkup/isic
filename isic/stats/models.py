from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.query_utils import Q
from django_extensions.db.fields import CreationDateTimeField
from django_extensions.db.models import TimeStampedModel

from isic.core.models import Image


class GaMetrics(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name="range_end_gt_range_start", check=Q(range_start__lt=F("range_end"))
            )
        ]

    range_start = models.DateTimeField()
    range_end = models.DateTimeField()
    # this number can be greater than the sum of sessions_per_country because
    # there are certain number of sessions where the country is unknown.
    num_sessions = models.PositiveIntegerField()
    sessions_per_country = models.JSONField()


class ImageDownload(models.Model):
    created = CreationDateTimeField()
    download_time = models.DateTimeField()
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(null=True, max_length=400)
    request_id = models.CharField(max_length=200)
    image = models.ForeignKey(Image, on_delete=models.PROTECT, related_name="downloads")

    class Meta:
        constraints = [
            CheckConstraint(
                name="download_occurred_before_tracking", check=Q(download_time__lt=F("created"))
            ),
            UniqueConstraint(name="unique_request_id", fields=["request_id"]),
        ]

    def __str__(self):
        return f"{self.ip_address} - {self.download_time}"
