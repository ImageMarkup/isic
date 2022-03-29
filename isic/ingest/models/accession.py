from copy import deepcopy
import io
from mimetypes import guess_type
import tempfile

import PIL.Image
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models, transaction
from django.db.models import JSONField, Transform
from django.db.models.aggregates import Count
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.query_utils import Q
from isic_metadata.metadata import MetadataRow
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel
from isic.ingest.models.cohort import Cohort
from isic.ingest.utils.mime import guess_mime_type
from isic.ingest.utils.zip import Blob

from .zip_upload import ZipUpload

ACCESSION_CHECKS = {
    'quality_check': {
        'short_name': 'Quality',
        'nice_name': 'Quality Check',
    },
    'diagnosis_check': {'short_name': 'Diagnosis', 'nice_name': 'Diagnosis Check'},
    'phi_check': {'short_name': 'PHI', 'nice_name': 'PHI Check'},
    'duplicate_check': {'short_name': 'Duplicate', 'nice_name': 'Duplicate Check'},
    'lesion_check': {'short_name': 'Lesion IDs', 'nice_name': 'Lesion ID Check'},
}


class Approx(Transform):
    lookup_name = 'approx'

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return 'ROUND(CAST(%s as float) / 5.0) * 5' % lhs, params


JSONField.register_lookup(Approx)


class InvalidBlobError(Exception):
    pass


class AccessionStatus(models.TextChoices):
    CREATING = 'creating', 'Creating'
    CREATED = 'created', 'Created'
    SKIPPED = 'skipped', 'Skipped'
    FAILED = 'failed', 'Failed'
    SUCCEEDED = 'succeeded', 'Succeeded'


class Accession(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        # A blob_name is unique at the *cohort* level, which also makes it unique at the zip
        # level.
        unique_together = [['cohort', 'blob_name']]

        constraints = [
            # girder_id should be unique among nonempty girder_id values
            UniqueConstraint(
                name='accession_unique_girder_id', fields=['girder_id'], condition=~Q(girder_id='')
            ),
            # require blob_size / width / height for succeeded accessions
            CheckConstraint(
                name='accession_succeeded_blob_fields',
                check=Q(
                    status=AccessionStatus.SUCCEEDED,
                    blob_size__isnull=False,
                    width__isnull=False,
                    height__isnull=False,
                )
                | ~Q(status=AccessionStatus.SUCCEEDED),
            ),
        ]

    # the creator is either inherited from the zip creator, or directly attached in the
    # case of a single shot upload.
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name='accessions')
    girder_id = models.CharField(
        blank=True, max_length=24, help_text='The image_id from Girder.', db_index=True
    )
    zip_upload = models.ForeignKey(
        ZipUpload, on_delete=models.CASCADE, null=True, related_name='accessions'
    )
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name='accessions')

    # the original blob is stored in case blobs need to be reprocessed
    original_blob = S3FileField()

    # blob_name has to be indexed because metadata selection does large
    # WHERE blob_name IN (...) queries
    blob_name = models.CharField(max_length=255, db_index=True, editable=False)

    # When instantiated, blob is empty, as it holds the EXIF-stripped image
    blob = S3FileField(blank=True)
    # nullable unless status is succeeded
    blob_size = models.PositiveBigIntegerField(null=True, default=None, editable=False)
    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)

    status = models.CharField(
        choices=AccessionStatus.choices, max_length=20, default=AccessionStatus.CREATING
    )

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

    def generate_blob(self):
        """
        Generate `blob` and set `blob_size`, `height`, `width`.

        This is idempotent.
        The Accession will be saved and `status` will be updated appropriately.
        """
        try:
            with self.original_blob.open('rb') as original_blob_stream:
                blob_mime_type = guess_mime_type(original_blob_stream, self.blob_name)
            blob_major_mime_type = blob_mime_type.partition('/')[0]
            if blob_major_mime_type != 'image':
                raise InvalidBlobError(f'Blob has a non-image MIME type: "{blob_mime_type}"')

            # Set a larger max size, to accommodate confocal images
            # This uses ~1.1GB of memory
            PIL.Image.MAX_IMAGE_PIXELS = 20_000 * 20_000 * 3
            try:
                img = PIL.Image.open(original_blob_stream)
            except PIL.Image.UnidentifiedImageError:
                raise InvalidBlobError('Blob cannot be recognized by PIL.')

            # Explicitly load the image, so any decoding errors can be caught
            try:
                img.load()
            except OSError as e:
                if 'image file is truncated' in str(e):
                    raise InvalidBlobError('Blob appears truncated.')
                else:
                    # Any other errors are not expected, so re-raise them natively
                    raise

            # Strip any alpha channel
            img = img.convert('RGB')

            with tempfile.SpooledTemporaryFile() as stripped_blob_stream:
                img.save(stripped_blob_stream, format='JPEG')

                stripped_blob_stream.seek(0, io.SEEK_END)
                stripped_blob_size = stripped_blob_stream.tell()
                stripped_blob_stream.seek(0)

                self.blob = InMemoryUploadedFile(
                    file=stripped_blob_stream,
                    field_name=None,
                    name=self.blob_name,
                    content_type='image/jpeg',
                    size=stripped_blob_size,
                    charset=None,
                )
                self.blob_size = stripped_blob_size
                self.height = img.height
                self.width = img.width

                self.save(update_fields=['blob', 'blob_size', 'height', 'width'])

        except InvalidBlobError:
            self.status = AccessionStatus.SKIPPED
            self.save(update_fields=['status'])
            # Expected failure, so return cleanly
        except Exception:
            self.status = AccessionStatus.FAILED
            self.save(update_fields=['status'])
            # Unexpected failure, so re-raise
            raise
        else:
            self.status = AccessionStatus.SUCCEEDED
            self.save(update_fields=['status'])

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

    @classmethod
    def from_blob(cls, blob: Blob):
        blob_content_type = guess_type(blob.name)[0]
        # TODO: Store content_type in the DB?
        return cls(
            blob_name=blob.name,
            # Use an InMemoryUploadedFile instead of a SimpleUploadedFile, since
            # we can explicitly know the size and don't need the stream to be
            # wrapped
            original_blob=InMemoryUploadedFile(
                file=blob.stream,
                field_name=None,
                name=blob.name,
                content_type=blob_content_type,
                size=blob.size,
                charset=None,
            ),
        )

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
    def check_counts(cohort):
        from .distinctness_measure import DistinctnessMeasure

        duplicate_checksums = (
            DistinctnessMeasure.objects.filter(
                accession__cohort=cohort,
                checksum__in=DistinctnessMeasure.objects.values('checksum')
                .annotate(is_duplicate=Count('checksum'))
                .filter(accession__cohort=cohort, is_duplicate__gt=1)
                .values_list('checksum', flat=True),
            )
            .order_by('checksum')
            .values_list('checksum', flat=True)
        )
        return {
            'phi_check': Accession.objects.filter(cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(phi_check=None), distinct=True),
                accepted=Count('pk', filter=Q(phi_check=True), distinct=True),
                rejected=Count('pk', filter=Q(phi_check=False), distinct=True),
            ),
            'quality_check': Accession.objects.filter(cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(quality_check=None), distinct=True),
                accepted=Count('pk', filter=Q(quality_check=True), distinct=True),
                rejected=Count('pk', filter=Q(quality_check=False), distinct=True),
            ),
            'diagnosis_check': Accession.objects.filter(cohort=cohort).aggregate(
                unreviewed=Count('pk', filter=Q(diagnosis_check=None), distinct=True),
                accepted=Count('pk', filter=Q(diagnosis_check=True), distinct=True),
                rejected=Count('pk', filter=Q(diagnosis_check=False), distinct=True),
            ),
            'duplicate_check': Accession.objects.filter(
                cohort=cohort, distinctnessmeasure__checksum__in=duplicate_checksums
            ).aggregate(
                unreviewed=Count('pk', filter=Q(duplicate_check=None), distinct=True),
                accepted=Count('pk', filter=Q(duplicate_check=True), distinct=True),
                rejected=Count('pk', filter=Q(duplicate_check=False), distinct=True),
            ),
            'lesion_check': Accession.objects.filter(
                cohort=cohort, metadata__lesion_id__isnull=False
            ).aggregate(
                unreviewed=Count('pk', filter=Q(lesion_check=None), distinct=True),
                accepted=Count('pk', filter=Q(lesion_check=True), distinct=True),
                rejected=Count('pk', filter=Q(lesion_check=False), distinct=True),
            ),
        }

    @property
    def age_approx(self) -> int | None:
        return int(round(self.metadata['age'] / 5.0) * 5) if 'age' in self.metadata else None

    @property
    def redacted_metadata(self) -> dict:
        from isic.core.models.image import RESTRICTED_METADATA_FIELDS

        redacted = dict(self.metadata)

        if 'age' in self.metadata:
            redacted['age_approx'] = self.age_approx

        for f in RESTRICTED_METADATA_FIELDS:
            if f in redacted:
                del redacted[f]

        return redacted

    def _metadata_mutable_check(self):
        if hasattr(self, 'image'):
            raise ValidationError("Can't modify the accession as it already has an image.")

    def update_metadata(self, user: User, csv_row: dict, *, ignore_image_check=False):
        """
        Apply metadata to an accession from a row in a CSV.

        ALL metadata modifications must go through update_metadata since it handles checking if the
        metadata can be mutated and they create version records.

        This method only supports adding/modifying metadata (e.g. dict.update).
        """
        if self.pk and not ignore_image_check:
            self._metadata_mutable_check()

        # merge metadata with existing metadata, this is necessary for metadata
        # that has interdependent checks.
        existing_metadata = deepcopy(self.metadata)
        existing_metadata.update(csv_row)
        metadata = MetadataRow.parse_obj(existing_metadata)
        with transaction.atomic():
            self.unstructured_metadata.update(metadata.unstructured)
            self.metadata.update(
                metadata.dict(exclude_unset=True, exclude_none=True, exclude={'unstructured'})
            )
            self.metadata_versions.create(
                creator=user,
                metadata=self.metadata,
                unstructured_metadata=self.unstructured_metadata,
            )
            # TODO: this method could result in duplicate identical versions
            self.save(update_fields=['metadata', 'unstructured_metadata'])
            self.save(update_fields=['metadata', 'unstructured_metadata'])
