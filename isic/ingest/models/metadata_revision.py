from django.contrib.auth.models import User
from django.db import models

from isic.core.models import CreationSortedTimeStampedModel

from .accession import Accession


class MetadataRevision(CreationSortedTimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='metadata_revisions')
    accession = models.ForeignKey(
        Accession, on_delete=models.PROTECT, related_name='metadata_revisions'
    )
    metadata = models.JSONField()
    unstructured_metadata = models.JSONField()
