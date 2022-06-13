from copy import deepcopy
import io
from mimetypes import guess_type
import tempfile
from uuid import uuid4

import PIL.Image
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models, transaction
from django.db.models import JSONField, Transform
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.query_utils import Q
from isic_metadata.metadata import MetadataRow
from s3_file_field import S3FileField

from isic.core.models import CreationSortedTimeStampedModel
from isic.ingest.models.cohort import Cohort
from isic.ingest.utils.mime import guess_mime_type
from isic.ingest.utils.zip import Blob

from .zip_upload import ZipUpload


class Approx(Transform):
    lookup_name = 'approx'

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return 'ROUND(CAST(%s as float) / 5.0) * 5' % lhs, params


JSONField.register_lookup(Approx)


class InvalidBlobError(Exception):
    pass


class AccessionQuerySet(models.QuerySet):
    def ingesting(self):
        return self.exclude(
            Q(status=AccessionStatus.SUCCEEDED)
            | Q(status=AccessionStatus.FAILED)
            | Q(status=AccessionStatus.SKIPPED)
        )

    def uningested(self):
        return self.filter(Q(status=AccessionStatus.FAILED) | Q(status=AccessionStatus.SKIPPED))

    def ingested(self):
        return self.filter(status=AccessionStatus.SUCCEEDED)

    def unpublished(self):
        return self.filter(image__isnull=True)

    def published(self):
        return self.filter(image__isnull=False)

    def publishable(self):
        return self.accepted()

    def reviewable(self):
        return self.ingested().unpublished()

    def unreviewable(self):
        return self.unpublished().exclude(status=AccessionStatus.SUCCEEDED)

    def unreviewed(self):
        return self.reviewable().filter(review=None)

    def reviewed(self):
        return self.reviewable().exclude(review=None)

    def accepted(self):
        return self.reviewable().filter(review__value=True)

    def rejected(self):
        return self.reviewable().filter(review__value=False)


class AccessionStatus(models.TextChoices):
    CREATING = 'creating', 'Creating'
    CREATED = 'created', 'Created'
    SKIPPED = 'skipped', 'Skipped'
    FAILED = 'failed', 'Failed'
    SUCCEEDED = 'succeeded', 'Succeeded'


class Accession(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        # original_blob_name is unique at the *cohort* level, which also makes it unique at the zip
        # level.
        unique_together = [['cohort', 'original_blob_name']]

        constraints = [
            # girder_id should be unique among nonempty girder_id values
            UniqueConstraint(
                name='accession_unique_girder_id', fields=['girder_id'], condition=~Q(girder_id='')
            ),
            # blob should be unique when it's filled out
            UniqueConstraint(name='accession_unique_blob', fields=['blob'], condition=~Q(blob='')),
            # the original blob name should always be hidden, so blob_name shouldn't be the same
            CheckConstraint(
                name='accession_blob_name_not_original_blob_name',
                check=~Q(original_blob_name=F('blob_name')),
            ),
            # require blob_size / width / height for succeeded accessions
            CheckConstraint(
                name='accession_succeeded_blob_fields',
                check=Q(
                    status=AccessionStatus.SUCCEEDED,
                    thumbnail_256_size__isnull=False,
                    blob_size__isnull=False,
                    width__isnull=False,
                    height__isnull=False,
                )
                & ~Q(thumbnail_256='', blob_name='')
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
    original_blob = S3FileField(unique=True)
    # the original blob name is stored and kept private in case of leaked data in filenames
    original_blob_name = models.CharField(max_length=255, db_index=True, editable=False)
    original_blob_size = models.PositiveBigIntegerField(editable=False)

    # When instantiated, blob is empty, as it holds the EXIF-stripped image
    # this isn't unique because of the blank case, see constraints above.
    blob = S3FileField(blank=True)
    # blob_name has to be indexed because metadata selection does large
    # WHERE blob_name IN (...) queries
    blob_name = models.CharField(max_length=255, db_index=True, editable=False, blank=True)
    # blob_size/width/height are nullable unless status is succeeded
    blob_size = models.PositiveBigIntegerField(null=True, default=None, editable=False)
    width = models.PositiveIntegerField(null=True)
    height = models.PositiveIntegerField(null=True)

    status = models.CharField(
        choices=AccessionStatus.choices, max_length=20, default=AccessionStatus.CREATING
    )

    thumbnail_256 = S3FileField(blank=True)
    thumbnail_256_size = models.PositiveIntegerField(null=True, default=None, editable=False)

    metadata = models.JSONField(default=dict)
    unstructured_metadata = models.JSONField(default=dict)

    objects = AccessionQuerySet.as_manager()

    def __str__(self) -> str:
        return self.blob_name

    @property
    def published(self):
        return hasattr(self, 'image')

    @property
    def reviewed(self):
        return hasattr(self, 'review')

    @property
    def unreviewed(self):
        return not self.reviewed

    def generate_blob(self):
        """
        Generate `blob` and set `blob_size`, `height`, `width`.

        This is idempotent.
        The Accession will be saved and `status` will be updated appropriately.
        """
        try:
            with self.original_blob.open('rb') as original_blob_stream:
                blob_mime_type = guess_mime_type(original_blob_stream, self.original_blob_name)
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

                self.blob_name = f'{uuid4()}.jpg'
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

            self.generate_thumbnail()

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

            self.thumbnail_256_size = thumbnail_stream.getbuffer().nbytes
            self.thumbnail_256 = InMemoryUploadedFile(
                file=thumbnail_stream,
                field_name=None,
                name=(
                    f'{self.image.isic_id}_thumbnail_256.jpg'
                    if hasattr(self, 'image')
                    else 'thumbnail_256.jpg'
                ),
                content_type='image/jpeg',
                size=self.thumbnail_256_size,
                charset=None,
            )
            self.save(update_fields=['thumbnail_256', 'thumbnail_256_size'])

    @classmethod
    def from_blob(cls, blob: Blob):
        blob_content_type = guess_type(blob.name)[0]
        # TODO: Store content_type in the DB?
        return cls(
            original_blob_name=blob.name,
            original_blob_size=blob.size,
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
    def _age_approx(age: int) -> int:
        return int(round(age / 5.0) * 5)

    @property
    def age_approx(self) -> int | None:
        return self._age_approx(self.metadata['age']) if 'age' in self.metadata else None

    @staticmethod
    def _redact_metadata(metadata: dict) -> dict:
        from isic.core.models.image import RESTRICTED_METADATA_FIELDS

        if 'age' in metadata:
            metadata['age_approx'] = Accession._age_approx(metadata['age'])

        for f in RESTRICTED_METADATA_FIELDS:
            if f in metadata:
                del metadata[f]

        return metadata

    @property
    def redacted_metadata(self) -> dict:
        return self._redact_metadata(dict(self.metadata))

    def _require_unpublished(self):
        if self.published:
            raise ValidationError("Can't modify the accession as it's already been published.")

    def update_metadata(
        self, user: User, csv_row: dict, *, ignore_image_check=False, reset_review=True
    ):
        """
        Apply metadata to an accession from a row in a CSV.

        ALL metadata modifications must go through update_metadata/remove_metadata since they:
        1) Check to see if the accession can be modified
        2) Manage audit trails (MetadataVersion records)
        3) Reset the review
        """
        if self.pk and not ignore_image_check:
            self._require_unpublished()

        with transaction.atomic():
            modified = False

            # keep original copy so we only modify metadata if it changes
            original_metadata = deepcopy(self.metadata)
            # create second copy to avoid mutating self.metadata unless it will be changed
            metadata = deepcopy(self.metadata)
            # merge metadata with existing metadata, this is necessary for metadata
            # that has interdependent checks.
            metadata.update(csv_row)
            parsed_metadata = MetadataRow.parse_obj(metadata)

            # update unstructured metadata
            if (
                parsed_metadata.unstructured
                and self.unstructured_metadata != parsed_metadata.unstructured
            ):
                modified = True
                self.unstructured_metadata.update(parsed_metadata.unstructured)

            # update structured metadata
            new_metadata = parsed_metadata.dict(
                exclude_unset=True, exclude_none=True, exclude={'unstructured'}
            )
            if new_metadata and original_metadata != new_metadata:
                modified = True
                self.metadata.update(new_metadata)

                if reset_review:
                    # if a new metadata item has been added or an existing has been modified,
                    # reset the review state.
                    from isic.ingest.services.accession.review import accession_review_delete

                    accession_review_delete(accession=self)

            if modified:
                self.metadata_versions.create(
                    creator=user,
                    metadata=self.metadata,
                    unstructured_metadata=self.unstructured_metadata,
                )
                self.save()

    def remove_metadata(
        self, user: User, metadata_fields: list[str], *, ignore_image_check=False, reset_review=True
    ):
        """Remove metadata from an accession."""
        if self.pk and not ignore_image_check:
            self._require_unpublished()

        modified = False
        with transaction.atomic():
            for field in metadata_fields:
                if self.metadata.pop(field, None) is not None:
                    modified = True

                    if reset_review:
                        from isic.ingest.services.accession.review import accession_review_delete

                        accession_review_delete(accession=self)

                if self.unstructured_metadata.pop(field, None) is not None:
                    modified = True

            if modified:
                self.metadata_versions.create(
                    creator=user,
                    metadata=self.metadata,
                    unstructured_metadata=self.unstructured_metadata,
                )
                self.save()
