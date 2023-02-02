from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from .accession import Accession


class AccessionReview(models.Model):
    class Meta:
        ordering = ["-reviewed_at"]
        get_latest_by = "reviewed_at"

    accession = models.OneToOneField(Accession, on_delete=models.CASCADE, related_name="review")
    creator = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    reviewed_at = models.DateTimeField(default=timezone.now)
    value = models.BooleanField()
