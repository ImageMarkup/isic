import logging
from mimetypes import guess_type
import zipfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from django.core.validators import FileExtensionValidator
from django.db import models, transaction
from django.template.loader import render_to_string
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel
from isic.ingest.utils.zip import file_names_in_zip, items_in_zip

from .cohort import Cohort

logger = logging.getLogger(__name__)


class ZipUpload(CreationSortedTimeStampedModel):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        EXTRACTING = 'extracting', 'Extracting'
        EXTRACTED = 'extracted', 'Extracted'
        FAILED = 'failed', 'Failed'

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='zip_uploads')

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    blob = S3FileField(validators=[FileExtensionValidator(allowed_extensions=['zip'])])
    blob_name = models.CharField(max_length=255, editable=False)
    blob_size = models.PositiveBigIntegerField(editable=False)

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATED)

    def __str__(self) -> str:
        return self.blob_name

    def _get_preexisting_and_duplicates(self) -> tuple[list[str], list[str]]:
        from .accession import Accession

        blob_names_in_zip = set()

        blob_name_duplicates = set()
        with self.blob.open('rb') as zip_blob_stream:
            for original_filename in file_names_in_zip(zip_blob_stream):
                if original_filename in blob_names_in_zip:
                    blob_name_duplicates.add(original_filename)
                blob_names_in_zip.add(original_filename)

        blob_name_preexisting = Accession.objects.filter(
            cohort=self.cohort, blob_name__in=blob_names_in_zip
        ).values_list('blob_name', flat=True)

        return sorted(blob_name_preexisting), sorted(blob_name_duplicates)

    class ExtractError(Exception):
        pass

    class InvalidExtractError(ExtractError):
        pass

    class DuplicateExtractError(ExtractError):
        pass

    def extract(self):
        from .accession import AccessionStatus

        if self.status != ZipUpload.Status.CREATED:
            raise Exception('Can not extract zip %d with status %s', self.pk, self.status)

        try:
            with transaction.atomic():
                self.status = ZipUpload.Status.EXTRACTING
                self.save(update_fields=['status'])

                blob_name_preexisting, blob_name_duplicates = self._get_preexisting_and_duplicates()
                if blob_name_preexisting or blob_name_duplicates:
                    raise ZipUpload.DuplicateExtractError(
                        blob_name_preexisting, blob_name_duplicates
                    )

                with self.blob.open('rb') as zip_blob_stream:
                    for zip_item in items_in_zip(zip_blob_stream):
                        zip_item_content_type = guess_type(zip_item.name)[0]
                        # TODO: Store content_type in the DB?
                        self.accessions.create(
                            cohort=self.cohort,
                            blob_name=zip_item.name,
                            # Use an InMemoryUploadedFile instead of a SimpleUploadedFile, since
                            # we can explicitly know the size and don't need the stream to be
                            # wrapped
                            original_blob=InMemoryUploadedFile(
                                file=zip_item.stream,
                                field_name=None,
                                name=zip_item.name,
                                content_type=zip_item_content_type,
                                size=zip_item.size,
                                charset=None,
                            ),
                        )

                self.accessions.update(status=AccessionStatus.CREATED)

        except zipfile.BadZipFile as e:
            logger.warning('Failed zip extraction: %d <%s>: invalid zip: %s', self.pk, self, e)
            self.status = ZipUpload.Status.FAILED
            raise ZipUpload.InvalidExtractError
        except ZipUpload.DuplicateExtractError:
            logger.warning('Failed zip extraction: %d <%s>: duplicates', self.pk, self)
            self.status = ZipUpload.Status.FAILED
            raise
        else:
            self.status = ZipUpload.Status.EXTRACTED
        finally:
            self.save(update_fields=['status'])

    def extract_and_notify(self):
        try:
            self.extract()
        except ZipUpload.InvalidExtractError:
            send_mail(
                'A problem processing your zip file',
                render_to_string(
                    'ingest/email/zip_invalid.txt',
                    {
                        'zip': self,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )
            raise
        except ZipUpload.DuplicateExtractError as e:
            blob_name_preexisting, blob_name_duplicates = e.args
            send_mail(
                'A problem processing your zip file',
                render_to_string(
                    'ingest/email/zip_duplicates.txt',
                    {
                        'zip': self,
                        'blob_name_preexisting': blob_name_preexisting,
                        'blob_name_duplicates': blob_name_duplicates,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )
            raise
        else:
            send_mail(
                'Zip file extracted',
                render_to_string(
                    'ingest/email/zip_success.txt',
                    {
                        'zip': self,
                    },
                ),
                settings.DEFAULT_FROM_EMAIL,
                [self.creator.email],
            )

    def reset(self):
        with transaction.atomic():
            self.accessions.all().delete()
            self.status = ZipUpload.Status.CREATED
            self.save(update_fields=['status'])
