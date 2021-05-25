from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel

from .accession import Accession


class DistinctnessMeasure(TimeStampedModel):
    accession = models.OneToOneField(Accession, on_delete=models.CASCADE)
    checksum = models.CharField(
        max_length=64,
        validators=[RegexValidator(r'^[0-9a-f]{64}$')],
        null=True,
        blank=True,
        editable=False,
        db_index=True,
    )

    def __str__(self) -> str:
        return self.checksum
