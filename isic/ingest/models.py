import os

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.urls.base import reverse
from django.utils.safestring import mark_safe
from django_extensions.db.models import TimeStampedModel
from s3_file_field import S3FileField


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
            'Text which must be reproduced by users of your images, to comply with Creative'
            'Commons Attribution requirements.'
        ),
    )

    def __str__(self) -> str:
        return self.institution_name


class Cohort(TimeStampedModel):
    creator = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    contributor = models.ForeignKey(Contributor, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text='The dataset_id from Girder.')

    name = models.CharField(max_length=255)
    description = models.TextField()

    copyright_license = models.CharField(choices=CopyrightLicense.choices, max_length=255)

    # required if copyright_license is CC-BY-*
    attribution = models.CharField(max_length=255)

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

    upload = models.ForeignKey('Zip', on_delete=models.CASCADE, related_name='accessions')

    # the original blob is stored in case blobs need to be reprocessed
    original_blob = S3FileField(null=True)
    # TODO: remove null after database on production is reset

    blob = S3FileField()
    # blob_name has to be indexed because metadata selection does large
    # WHERE blob_name IN (...) queries
    blob_name = models.CharField(max_length=255, db_index=True)
    blob_size = models.PositiveBigIntegerField()

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


class Zip(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        STARTED = 'extracting', 'Extracting'
        COMPLETED = 'extracted', 'Extracted'

    creator = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text='The batch_id from Girder.')

    cohort = models.ForeignKey(Cohort, null=True, on_delete=models.CASCADE, related_name='zips')

    blob = S3FileField(blank=True)
    blob_name = models.CharField(blank=True, max_length=255)
    blob_size = models.PositiveBigIntegerField(null=True)

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATED)

    def __str__(self) -> str:
        return self.blob_name

    @property
    def blob_basename(self) -> str:
        return os.path.basename(self.blob_name)

    def succeed(self):
        self.status = Zip.Status.COMPLETED
        self.save(update_fields=['status'])

    def reset(self):
        with transaction.atomic():
            self.accessions.all().delete()
            self.status = Zip.Status.CREATED
            self.save(update_fields=['status'])
