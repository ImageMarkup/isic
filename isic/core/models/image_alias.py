from django.db import models
from django_extensions.db.models import TimeStampedModel

from .image import Image
from .isic_id import IsicId


class ImageAlias(TimeStampedModel):
    class Meta:
        verbose_name_plural = "Image aliases"

    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    image = models.ForeignKey(Image, on_delete=models.PROTECT, related_name="aliases")
