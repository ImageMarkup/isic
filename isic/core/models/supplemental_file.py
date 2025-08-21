from pathlib import PurePosixPath

from django.db import models
from s3_file_field import S3FileField

from isic.core.models.doi import Doi, DraftDoi


class AbstractSupplementalFile(models.Model):
    blob = S3FileField()
    description = models.CharField(max_length=255)
    filename = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["order"]

    def __str__(self):
        return self.filename

    def extension(self):
        return PurePosixPath(self.filename).suffix.replace(".", "")


class SupplementalFile(AbstractSupplementalFile):
    doi = models.ForeignKey(Doi, on_delete=models.CASCADE, related_name="supplemental_files")


class DraftSupplementalFile(AbstractSupplementalFile):
    doi = models.ForeignKey(DraftDoi, on_delete=models.CASCADE, related_name="supplemental_files")
