from django.db import models
from django_extensions.db.models import TimeStampedModel

from isic.core.models import Image
from isic.core.models.base import CreationSortedTimeStampedModel


class GaMetrics(TimeStampedModel):
    range_start = models.DateTimeField()
    range_end = models.DateTimeField()
    # this number can be greater than the sum of sessions_per_country because
    # there are certain number of sessions where the country is unknown.
    num_sessions = models.IntegerField()
    sessions_per_country = models.JSONField()


class ImageDownload(CreationSortedTimeStampedModel):
    download_time = models.DateTimeField()
    ip_address = models.GenericIPAddressField()
    request_id = models.CharField(unique=True, max_length=200)
    image = models.ForeignKey(Image, on_delete=models.PROTECT, related_name='downloads')
