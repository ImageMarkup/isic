from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField
from django_extensions.db.models import TimeStampedModel

from .image import IsicIdField


class DuplicateImage(TimeStampedModel):
    accession = models.ForeignKey(
        'ingest.Accession', on_delete=models.CASCADE, related_name='duplicates'
    )
    girder_id = models.CharField(
        max_length=24,
        unique=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    isic_id = IsicIdField()
    metadata = JSONField(default=dict)


class ImageRedirect(TimeStampedModel):
    isic_id = IsicIdField()
    image = models.ForeignKey('Image', on_delete=models.PROTECT, related_name='redirects')
