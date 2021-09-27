from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

from isic.core.constants import MONGO_ID_REGEX
from isic.ingest.models import Accession

from .image import Image
from .isic_id import IsicId


class DuplicateImage(TimeStampedModel):
    accession = models.ForeignKey(Accession, on_delete=models.CASCADE, related_name='duplicates')
    girder_id = models.CharField(
        max_length=24,
        unique=True,
        validators=[RegexValidator(f'^{MONGO_ID_REGEX}$')],
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    metadata = models.JSONField(default=dict)


class ImageAlias(TimeStampedModel):
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    image = models.ForeignKey(Image, on_delete=models.PROTECT, related_name='aliases')
