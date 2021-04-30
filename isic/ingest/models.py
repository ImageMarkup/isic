import logging
from mimetypes import guess_type
from typing import List, Tuple
import zipfile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.mail import send_mail
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.template.loader import render_to_string
from django.urls.base import reverse
from django.utils.safestring import mark_safe
from django_extensions.db.models import TimeStampedModel
import numpy as np
import pandas as pd
from s3_file_field import S3FileField

from isic.ingest.zip_utils import file_names_in_zip, items_in_zip

logger = logging.getLogger(__name__)


class CopyrightLicense(models.TextChoices):
    CC_0 = ('CC-0', 'CC-0')

    # These 2 require attribution
    CC_BY = ('CC-BY', 'CC-BY')
    CC_BY_NC = ('CC-BY-NC', 'CC-BY-NC')


class Contributor(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    institution_name = models.CharField(
        max_length=255,
        verbose_name='Institution Name',
        help_text=mark_safe(
            'The full name of your affiliated institution. <strong>This is private</strong>, '
            'and will not be published along with your images.'
        ),
    )
    institution_url = models.URLField(
        blank=True,
        verbose_name='Institution URL',
        help_text=mark_safe(
            'The URL of your affiliated institution. <strong>This is private</strong>, and '
            'will not be published along with your images.'
        ),
    )
    legal_contact_info = models.TextField(
        verbose_name='Legal Contact Information',
        help_text=mark_safe(
            'The person or institution responsible for legal inquiries about your data. '
            '<strong> This is private</strong>, and will not be published along with your images.'
        ),
    )
    default_copyright_license = models.CharField(
        choices=CopyrightLicense.choices,
        max_length=255,
        blank=True,
        verbose_name='Default Copyright License',
    )
    default_attribution = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Default Attribution',
        help_text=mark_safe(
            'Text which must be reproduced by users of your images, to comply with Creative '
            'Commons Attribution requirements.'
        ),
    )

    def __str__(self) -> str:
        return self.institution_name


class Cohort(TimeStampedModel):
    contributor = models.ForeignKey(Contributor, on_delete=models.PROTECT)
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text='The dataset_id from Girder.')

    name = models.CharField(
        max_length=255,
        help_text=mark_safe(
            'The name of your Cohort. '
            '<strong>This is private</strong>, and will '
            'not be published along with your images.'
        ),
    )
    description = models.TextField(
        help_text=mark_safe(
            'The description of your Cohort.'
            '<strong>This is private</strong>, and will not be published along '
            'with your images.'
        )
    )

    copyright_license = models.CharField(choices=CopyrightLicense.choices, max_length=255)

    # required if copyright_license is CC-BY-*
    attribution = models.TextField()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse('cohort-detail', args=[self.id])


class MetadataFile(TimeStampedModel):
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='metadata_files')

    blob = S3FileField()
    blob_name = models.CharField(max_length=255)
    blob_size = models.PositiveBigIntegerField()

    def to_df(self):
        with self.blob.open() as csv:
            df = pd.read_csv(csv, header=0)

        # pydantic expects None for the absence of a value, not NaN
        df = df.replace({np.nan: None})

        return df


class Accession(TimeStampedModel):
    class Status(models.TextChoices):
        CREATING = 'creating', 'Creating'
        CREATED = 'created', 'Created'
        SKIPPED = 'skipped', 'Skipped'
        FAILED = 'failed', 'Failed'
        SUCCEEDED = 'succeeded', 'Succeeded'

    class Meta:
        # A blob_name is unique at the *cohort* level, but that's not possible to enforce at the
        # database layer. At least enforce the blob_name being unique at the zip level.
        # TODO: How to properly enforce cohort, blob_name uniqueness at the app layer.
        unique_together = [['upload', 'blob_name']]

    girder_id = models.CharField(blank=True, max_length=24, help_text='The image_id from Girder.')
    upload = models.ForeignKey('Zip', on_delete=models.CASCADE, related_name='accessions')

    # the original blob is stored in case blobs need to be reprocessed
    original_blob = S3FileField()

    # blob_name has to be indexed because metadata selection does large
    # WHERE blob_name IN (...) queries
    blob_name = models.CharField(max_length=255, db_index=True)

    # When instantiated, blob is empty, as it holds the EXIF-stripped image
    blob = S3FileField(blank=True)
    blob_size = models.PositiveBigIntegerField(null=True, default=None)

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATING)

    # required checks
    quality_check = models.BooleanField(null=True)
    diagnosis_check = models.BooleanField(null=True)
    phi_check = models.BooleanField(null=True)

    # checks that are only applicable to a subset of a cohort
    duplicate_check = models.BooleanField(null=True)
    lesion_check = models.BooleanField(null=True)

    metadata = JSONField(default=dict)
    unstructured_metadata = JSONField(default=dict)

    @staticmethod
    def checks():
        return {
            'quality_check': 'Quality',
            'diagnosis_check': 'Diagnosis',
            'phi_check': 'PHI',
            'duplicate_check': 'Duplicate',
            'lesion_check': 'Lesion IDs',
        }

    @staticmethod
    def check_counts(cohort):
        aggregates = {}
        ret = {}
        for check in Accession.checks():
            filters = Q(upload__cohort=cohort)

            if check == 'duplicate_check':
                duplicate_checksums = (
                    DistinctnessMeasure.objects.filter(
                        accession__upload__cohort=cohort,
                        checksum__in=DistinctnessMeasure.objects.values('checksum')
                        .annotate(is_duplicate=Count('checksum'))
                        .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
                        .values_list('checksum', flat=True),
                    )
                    .order_by('checksum')
                    .distinct('checksum')
                    .values_list('checksum', flat=True)
                )
                filters &= Q(distinctnessmeasure__checksum__in=duplicate_checksums)
            elif check == 'lesion_check':
                filters &= Q(metadata__lesion_id__isnull=False)

            aggregates.update(
                {
                    f'{check}_unreviewed': Count(
                        1, filter=filters & Q(**{f'{check}__isnull': True})
                    ),
                    f'{check}_rejected': Count(1, filter=filters & Q(**{check: False})),
                    f'{check}_accepted': Count(1, filter=filters & Q(**{check: True})),
                }
            )

        result = Accession.objects.aggregate(**aggregates)
        for check in Accession.checks():
            ret[check] = [
                result[f'{check}_unreviewed'],
                result[f'{check}_rejected'],
                result[f'{check}_accepted'],
            ]

        return ret


class DistinctnessMeasure(TimeStampedModel):
    accession = models.OneToOneField(Accession, on_delete=models.CASCADE)
    checksum = models.CharField(
        max_length=64, validators=[RegexValidator(r'^[0-9a-f]{64}$')], null=True, blank=True
    )


class CheckLog(TimeStampedModel):
    accession = models.ForeignKey(Accession, on_delete=models.PROTECT, related_name='checklogs')
    creator = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    change_field = models.CharField(max_length=255)
    change_to = models.BooleanField(null=True)


class Zip(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        EXTRACTING = 'extracting', 'Extracting'
        EXTRACTED = 'extracted', 'Extracted'
        FAILED = 'failed', 'Failed'

    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='zips')

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    blob = S3FileField()
    blob_name = models.CharField(max_length=255)
    blob_size = models.PositiveBigIntegerField()

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATED)

    def __str__(self) -> str:
        return self.blob_name

    def _get_preexisting_and_duplicates(self) -> Tuple[List[str], List[str]]:
        blob_names_in_zip = set()

        blob_name_duplicates = set()
        with self.blob.open('rb') as zip_blob_stream:
            for original_filename in file_names_in_zip(zip_blob_stream):
                if original_filename in blob_names_in_zip:
                    blob_name_duplicates.add(original_filename)
                blob_names_in_zip.add(original_filename)

        blob_name_preexisting = Accession.objects.filter(
            upload__cohort=self.cohort, blob_name__in=blob_names_in_zip
        ).values_list('blob_name', flat=True)

        return sorted(blob_name_preexisting), sorted(blob_name_duplicates)

    class ExtractException(Exception):
        pass

    class InvalidExtractException(ExtractException):
        pass

    class DuplicateExtractException(ExtractException):
        pass

    def extract(self):
        if self.status != Zip.Status.CREATED:
            raise Exception('Can not extract zip %d with status %s', self.pk, self.status)

        try:
            with transaction.atomic():
                self.status = Zip.Status.EXTRACTING
                self.save(update_fields=['status'])

                blob_name_preexisting, blob_name_duplicates = self._get_preexisting_and_duplicates()
                if blob_name_preexisting or blob_name_duplicates:
                    raise Zip.DuplicateExtractException(blob_name_preexisting, blob_name_duplicates)

                with self.blob.open('rb') as zip_blob_stream:
                    for zip_item in items_in_zip(zip_blob_stream):
                        zip_item_content_type = guess_type(zip_item.name)[0]
                        # TODO: Store content_type in the DB?
                        self.accessions.create(
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

                self.accessions.update(status=Accession.Status.CREATED)

        except zipfile.BadZipFile:
            logger.warning('Failed zip extraction: %d <%s>: invalid zip', self.pk, str(self))
            self.status = Zip.Status.FAILED
            raise Zip.InvalidExtractException
        except Zip.DuplicateExtractException:
            logger.warning('Failed zip extraction: %d <%s>: duplicates', self.pk, str(self))
            self.status = Zip.Status.FAILED
            raise
        else:
            self.status = Zip.Status.EXTRACTED
        finally:
            self.save(update_fields=['status'])

    def extract_and_notify(self):
        try:
            self.extract()
        except Zip.InvalidExtractException:
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
        except Zip.DuplicateExtractException as e:
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
            self.status = Zip.Status.CREATED
            self.save(update_fields=['status'])
