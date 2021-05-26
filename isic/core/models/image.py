from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.ingest.models import Accession

from .isic_id import IsicId


class Image(TimeStampedModel):
    accession = models.OneToOneField(
        Accession,
        on_delete=models.PROTECT,
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, default=IsicId.safe_create)

    public = models.BooleanField(default=False)

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse('core/image-detail', args=[self.pk])
