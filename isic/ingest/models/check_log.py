from django.contrib.auth.models import User
from django.db import models

from isic.core.models import CreationSortedTimeStampedModel

from .accession import Accession


class CheckLog(CreationSortedTimeStampedModel):
    accession = models.ForeignKey(Accession, on_delete=models.PROTECT, related_name='checklogs')
    creator = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    change_field = models.CharField(max_length=255)
    change_to = models.BooleanField(null=True)
