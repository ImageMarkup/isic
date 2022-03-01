from django.db import models
from django_extensions.db.models import TimeStampedModel


class GaMetrics(TimeStampedModel):
    range_start = models.DateTimeField()
    range_end = models.DateTimeField()
    num_sessions = models.IntegerField()
    sessions_per_country = models.JSONField()
