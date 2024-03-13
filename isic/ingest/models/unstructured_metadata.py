from django.db import models

from isic.ingest.models.accession import Accession


class UnstructuredMetadata(models.Model):
    accession = models.OneToOneField(
        Accession, on_delete=models.CASCADE, related_name="unstructured_metadata"
    )
    value = models.JSONField(default=dict, blank=True)
