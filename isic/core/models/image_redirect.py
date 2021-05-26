from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField
from django_extensions.db.models import TimeStampedModel

from isic.ingest.models import Accession

from .image import Image
from .isic_id import IsicId


class DuplicateImage(TimeStampedModel):
    accession = models.ForeignKey(Accession, on_delete=models.CASCADE, related_name='duplicates')
    girder_id = models.CharField(
        max_length=24,
        unique=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT)
    metadata = JSONField(default=dict)


class ImageRedirect(TimeStampedModel):
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT)
    image = models.ForeignKey(Image, on_delete=models.PROTECT, related_name='redirects')
