from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField
from django_extensions.db.models import TimeStampedModel


class DuplicateImage(TimeStampedModel):
    accession = models.ForeignKey(
        'ingest.Accession', on_delete=models.CASCADE, related_name='duplicates', null=True
    )
    girder_id = models.CharField(
        max_length=24,
        unique=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    isic_id = models.CharField(
        max_length=12, validators=[RegexValidator(r'^ISIC_[0-9]{7}$')], unique=True
    )
    metadata = JSONField(default=dict)
