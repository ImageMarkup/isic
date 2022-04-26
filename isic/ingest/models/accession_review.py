from django.contrib.auth.models import User
from django.db import models

from isic.core.models import CreationSortedTimeStampedModel

from .accession import Accession


class AccessionReview(CreationSortedTimeStampedModel):
    accession = models.OneToOneField(Accession, on_delete=models.CASCADE, related_name='review')
    creator = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    reviewed_at = models.DateTimeField()
    value = models.BooleanField()
