import logging
import zipfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.db.models.constraints import UniqueConstraint
from django.db.models.query_utils import Q
from django.template.loader import render_to_string
from s3_file_field import S3FileField
import sentry_sdk

from isic.core.models import CreationSortedTimeStampedModel
from isic.ingest.utils.zip import file_names_in_zip, items_in_zip

from .cohort import Cohort

logger = logging.getLogger(__name__)


class ZipUpload(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        constraints = [
            UniqueConstraint(name="zipupload_unique_blob", fields=["blob"], condition=~Q(blob="")),
        ]

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        EXTRACTING = "extracting", "Extracting"
        EXTRACTED = "extracted", "Extracted"
        FAILED = "failed", "Failed"

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="zip_uploads")

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    blob = S3FileField(validators=[FileExtensionValidator(allowed_extensions=["zip"])])
    blob_name = models.CharField(max_length=255, editable=False)
    blob_size = models.PositiveBigIntegerField(editable=False)

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATED)

    def __str__(self) -> str:
        return self.blob_name

    def _get_preexisting_and_duplicates(self) -> tuple[list[str], list[str]]:
        from .accession import Accession

        original_blob_names_in_zip = set()
        original_blob_name_duplicates = set()

        with self.blob.open("rb") as zip_blob_stream:
            for original_filename in file_names_in_zip(zip_blob_stream):
                if original_filename in original_blob_names_in_zip:
                    original_blob_name_duplicates.add(original_filename)
                original_blob_names_in_zip.add(original_filename)

        original_blob_name_preexisting = Accession.objects.filter(
            cohort=self.cohort, original_blob_name__in=original_blob_names_in_zip
        ).values_list("original_blob_name", flat=True)

        return sorted(original_blob_name_preexisting), sorted(original_blob_name_duplicates)

    class ExtractError(Exception):
        pass

    class InvalidExtractError(ExtractError):
        pass

    class DuplicateExtractError(ExtractError):
        pass

    def extract(self):
        from .accession import Accession, AccessionStatus

        if self.status != ZipUpload.Status.CREATED:
            raise Exception("Can not extract zip %d with status %s", self.pk, self.status)

        try:
            with transaction.atomic():
                self.status = ZipUpload.Status.EXTRACTING
                self.save(update_fields=["status"])

                (
                    original_blob_name_preexisting,
                    original_blob_name_duplicates,
                ) = self._get_preexisting_and_duplicates()
                if original_blob_name_preexisting or original_blob_name_duplicates:
                    raise ZipUpload.DuplicateExtractError(
                        original_blob_name_preexisting, original_blob_name_duplicates
                    )

                with self.blob.open("rb") as zip_blob_stream:
                    for zip_item in items_in_zip(zip_blob_stream):
                        accession = Accession.from_blob(zip_item)
                        accession.creator = self.creator
                        accession.cohort = self.cohort
                        self.accessions.add(accession, bulk=False)

                self.accessions.update(status=AccessionStatus.CREATED)

        except zipfile.BadZipFile as e:
            logger.warning("Failed zip extraction: %d <%s>: invalid zip: %s", self.pk, self, e)
            sentry_sdk.capture_exception(e)
            self.status = ZipUpload.Status.FAILED
            raise ZipUpload.InvalidExtractError
        except ZipUpload.DuplicateExtractError:
            logger.info("Failed zip extraction: %d <%s>: duplicates", self.pk, self)
            self.status = ZipUpload.Status.FAILED
            raise
        else:
            self.status = ZipUpload.Status.EXTRACTED
        finally:
            self.save(update_fields=["status"])

    def extract_and_notify(self):
        try:
            self.extract()
        except ZipUpload.InvalidExtractError:
            send_mail(
                "A problem processing your zip file",
                render_to_string(
                    "ingest/email/zip_invalid.txt",
                    {
                        "zip": self,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )
            raise
        except ZipUpload.DuplicateExtractError as e:
            original_blob_name_preexisting, original_blob_name_duplicates = e.args
            send_mail(
                "A problem processing your zip file",
                render_to_string(
                    "ingest/email/zip_duplicates.txt",
                    {
                        "zip": self,
                        "original_blob_name_preexisting": original_blob_name_preexisting,
                        "original_blob_name_duplicates": original_blob_name_duplicates,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )
            raise
        else:
            send_mail(
                "Zip file extracted",
                render_to_string(
                    "ingest/email/zip_success.txt",
                    {
                        "zip": self,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )

    def reset(self):
        with transaction.atomic():
            self.accessions.all().delete()
            self.status = ZipUpload.Status.CREATED
            self.save(update_fields=["status"])
