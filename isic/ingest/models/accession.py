import io
from typing import Optional

import PIL.Image
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models
from django.db.models.aggregates import Count
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.query_utils import Q
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel
from isic.ingest.models.cohort import Cohort

from .zip import Zip


class AccessionStatus(models.TextChoices):
    CREATING = 'creating', 'Creating'
    CREATED = 'created', 'Created'
    SKIPPED = 'skipped', 'Skipped'
    FAILED = 'failed', 'Failed'
    SUCCEEDED = 'succeeded', 'Succeeded'


class Accession(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        # A blob_name is unique at the *cohort* level, but that's not possible to enforce at the
        # database layer. At least enforce the blob_name being unique at the zip level.
        # TODO: How to properly enforce cohort, blob_name uniqueness at the app layer.
        unique_together = [['upload', 'blob_name']]

        constraints = [
            # girder_id should be unique among nonempty girder_id values
            UniqueConstraint(
                name='accession_unique_girder_id', fields=['girder_id'], condition=~Q(girder_id='')
            ),
            # require width/height for succeeded accessions
            CheckConstraint(
                name='accession_wh_status_check',
                check=Q(status=AccessionStatus.SUCCEEDED, width__isnull=False, height__isnull=False)
                | ~Q(status=AccessionStatus.SUCCEEDED),
            ),
        ]

    girder_id = models.CharField(
        blank=True, max_length=24, help_text='The image_id from Girder.', db_index=True
    )
    upload = models.ForeignKey(Zip, on_delete=models.CASCADE, null=True, related_name='accessions')
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='accessions')

    # the original blob is stored in case blobs need to be reprocessed
    original_blob = S3FileField()

    # blob_name has to be indexed because metadata selection does large
    # WHERE blob_name IN (...) queries
    blob_name = models.CharField(max_length=255, db_index=True, editable=False)

    # When instantiated, blob is empty, as it holds the EXIF-stripped image
    blob = S3FileField(blank=True)
    blob_size = models.PositiveBigIntegerField(null=True, default=None, editable=False)

    status = models.CharField(
        choices=AccessionStatus.choices, max_length=20, default=AccessionStatus.CREATING
    )

    # nullable unless status is succeeded
    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)

    thumbnail_256 = S3FileField(blank=True)

    # required checks
    quality_check = models.BooleanField(null=True, db_index=True)
    diagnosis_check = models.BooleanField(null=True, db_index=True)
    phi_check = models.BooleanField(null=True, db_index=True)

    # checks that are only applicable to a subset of a cohort
    duplicate_check = models.BooleanField(null=True, db_index=True)
    lesion_check = models.BooleanField(null=True, db_index=True)

    metadata = models.JSONField(default=dict)
    unstructured_metadata = models.JSONField(default=dict)

    def __str__(self) -> str:
        return self.blob_name

    def generate_thumbnail(self) -> None:
        with self.blob.open() as blob_stream:
            img: PIL.Image.Image = PIL.Image.open(blob_stream)
            # Load the image so the stream can be closed
            img.load()

        # LANCZOS provides the best anti-aliasing
        img.thumbnail((256, 256), resample=PIL.Image.LANCZOS)

        with io.BytesIO() as thumbnail_stream:
            # 75 quality uses ~55% as much space as 90 quality, with only a very slight drop in
            # perceptible quality
            img.save(thumbnail_stream, format='JPEG', quality=75, optimize=True)
            thumbnail_stream.seek(0)

            self.thumbnail_256 = InMemoryUploadedFile(
                file=thumbnail_stream,
                field_name=None,
                name=(
                    f'{self.image.isic_id}_thumbnail_256.jpg'
                    if hasattr(self, 'image')
                    else 'thumbnail_256.jpg'
                ),
                content_type='image/jpeg',
                size=thumbnail_stream.getbuffer().nbytes,
                charset=None,
            )
            self.save(update_fields=['thumbnail_256'])

    @staticmethod
    def rejected_filter():
        return (
            Q(quality_check=False)
            | Q(diagnosis_check=False)
            | Q(phi_check=False)
            | Q(duplicate_check=False)
            | Q(lesion_check=False)
        )

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
        from .distinctness_measure import DistinctnessMeasure

        duplicate_checksums = (
            DistinctnessMeasure.objects.filter(
                accession__upload__cohort=cohort,
                checksum__in=DistinctnessMeasure.objects.values('checksum')
                .annotate(is_duplicate=Count('checksum'))
                .filter(accession__upload__cohort=cohort, is_duplicate__gt=1)
                .values_list('checksum', flat=True),
            )
            .order_by('checksum')
            .values_list('checksum', flat=True)
        )
        return {
            'phi_check': Accession.objects.filter(upload__cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(phi_check=None), distinct=True),
                accepted=Count('pk', filter=Q(phi_check=True), distinct=True),
                rejected=Count('pk', filter=Q(phi_check=False), distinct=True),
            ),
            'quality_check': Accession.objects.filter(upload__cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(quality_check=None), distinct=True),
                accepted=Count('pk', filter=Q(quality_check=True), distinct=True),
                rejected=Count('pk', filter=Q(quality_check=False), distinct=True),
            ),
            'diagnosis_check': Accession.objects.filter(upload__cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(diagnosis_check=None), distinct=True),
                accepted=Count('pk', filter=Q(diagnosis_check=True), distinct=True),
                rejected=Count('pk', filter=Q(diagnosis_check=False), distinct=True),
            ),
            'duplicate_check': Accession.objects.filter(
                upload__cohort=cohort, distinctnessmeasure__checksum__in=duplicate_checksums
            ).aggregate(
                unreviewed=Count('pk', filter=Q(duplicate_check=None), distinct=True),
                accepted=Count('pk', filter=Q(duplicate_check=True), distinct=True),
                rejected=Count('pk', filter=Q(duplicate_check=False), distinct=True),
            ),
            'lesion_check': Accession.objects.filter(
                upload__cohort=cohort, metadata__lesion_id__isnull=False
            ).aggregate(
                unreviewed=Count('pk', filter=Q(lesion_check=None), distinct=True),
                accepted=Count('pk', filter=Q(lesion_check=True), distinct=True),
                rejected=Count('pk', filter=Q(lesion_check=False), distinct=True),
            ),
        }

    @property
    def age_approx(self) -> Optional[int]:
        return int(round(self.metadata['age'] / 5.0) * 5) if 'age' in self.metadata else None
