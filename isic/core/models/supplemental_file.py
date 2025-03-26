from pathlib import PurePosixPath

from django.db import models
from s3_file_field import S3FileField

from isic.core.models.doi import Doi


class SupplementalFile(models.Model):
    """Supplemental files that can be attached to collections on DOI creation."""

    file = S3FileField()
    description = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    doi = models.ForeignKey(Doi, on_delete=models.CASCADE, related_name="supplemental_files")

    def __str__(self):
        return self.filename

    def extension(self):
        return PurePosixPath(self.filename).suffix.replace(".", "")
