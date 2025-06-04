import hashlib
from typing import IO

from django.core.validators import RegexValidator
from django.db import models

from .accession import Accession


class DistinctnessMeasure(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    accession = models.OneToOneField(Accession, on_delete=models.CASCADE)
    checksum = models.CharField(
        max_length=64,
        validators=[RegexValidator(r"^[0-9a-f]{64}$")],
        null=True,
        blank=True,
        editable=False,
    )

    def __str__(self) -> str:
        return self.checksum

    @staticmethod
    def compute_checksum(content: IO[bytes]) -> str:
        hash_obj = hashlib.sha256()
        # This initial seek is just defensive
        content.seek(0)
        while chunk := content.read(128 * hash_obj.block_size):
            hash_obj.update(chunk)
        content.seek(0)
        return hash_obj.hexdigest()
