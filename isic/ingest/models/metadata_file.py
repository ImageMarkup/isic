import csv
import io

from django.contrib.auth.models import User
from django.core.files.base import File
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models.query import QuerySet
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel

from .cohort import Cohort


class MetadataFile(CreationSortedTimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="metadata_files")

    blob = S3FileField(validators=[FileExtensionValidator(allowed_extensions=["csv"])], unique=True)
    blob_name = models.CharField(max_length=255, editable=False)
    blob_size = models.PositiveBigIntegerField(editable=False)

    validation_errors = models.TextField(blank=True)
    validation_completed = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.blob_name

    def to_iterable(self) -> tuple[File, csv.DictReader]:
        with self.blob.open("rb") as blob:
            encoded_blob = io.TextIOWrapper(blob, encoding="utf-8-sig")
            return encoded_blob, csv.DictReader(encoded_blob)


class MetadataFilePermissions:
    model = MetadataFile
    perms = ["view_metadatafile"]
    filters = {"view_metadatafile": "view_metadatafile_list"}

    @staticmethod
    def view_metadatafile_list(
        user_obj: User, qs: QuerySet[MetadataFile] | None = None
    ) -> QuerySet[MetadataFile]:
        qs = qs if qs is not None else MetadataFile._default_manager.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            return qs.filter(cohort__contributor__owners__in=[user_obj])

        return qs.none()

    @staticmethod
    def view_metadatafile(user_obj, obj):
        return MetadataFilePermissions.view_metadatafile_list(user_obj).contains(obj)


MetadataFile.perms_class = MetadataFilePermissions
