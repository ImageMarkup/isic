from copy import deepcopy
from dataclasses import dataclass
import io
import logging
from mimetypes import guess_type
import tempfile
from uuid import uuid4

from django.contrib.auth.models import User
from django.contrib.postgres.constraints import ExclusionConstraint
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import models, transaction
from django.db.models import Transform
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.fields import Field
from django.db.models.query_utils import Q
from isic_metadata.fields import ImageTypeEnum
from isic_metadata.metadata import MetadataRow
import PIL.Image
from s3_file_field import S3FileField

from isic.core.models import CopyrightLicense, CreationSortedTimeStampedModel
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.lesion import Lesion
from isic.ingest.models.patient import Patient
from isic.ingest.models.rcm_case import RcmCase
from isic.ingest.utils.mime import guess_mime_type
from isic.ingest.utils.zip import Blob

from .zip_upload import ZipUpload

logger = logging.getLogger(__name__)


class Approx(Transform):
    lookup_name = "approx"

    def as_sql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return f"ROUND(CAST({lhs} as float) / 5.0) * 5", params


Field.register_lookup(Approx)


class InvalidBlobError(Exception):
    pass


class AccessionMetadata(models.Model):
    concomitant_biopsy = models.BooleanField(null=True, blank=True)
    fitzpatrick_skin_type = models.CharField(max_length=255, null=True, blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=6, null=True, blank=True)
    anatom_site_general = models.CharField(max_length=255, null=True, blank=True)
    benign_malignant = models.CharField(max_length=255, null=True, blank=True)
    diagnosis = models.CharField(max_length=255, null=True, blank=True)
    diagnosis_confirm_type = models.CharField(max_length=255, null=True, blank=True)
    personal_hx_mm = models.BooleanField(null=True, blank=True)
    family_hx_mm = models.BooleanField(null=True, blank=True)
    clin_size_long_diam_mm = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    melanocytic = models.BooleanField(null=True, blank=True)

    mel_class = models.CharField(max_length=255, null=True, blank=True)
    mel_mitotic_index = models.CharField(max_length=255, null=True, blank=True)
    mel_thick_mm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    mel_type = models.CharField(max_length=255, null=True, blank=True)
    mel_ulcer = models.BooleanField(null=True, blank=True)

    acquisition_day = models.IntegerField(null=True, blank=True)

    nevus_type = models.CharField(max_length=255, null=True, blank=True)
    image_type = models.CharField(max_length=255, null=True, blank=True)
    dermoscopic_type = models.CharField(max_length=255, null=True, blank=True)
    tbp_tile_type = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        abstract = True


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


@dataclass(frozen=True)
class RemappedField:
    # csv_field_name is overloaded and refers to the field name in the incoming CSV,
    # the outgoing CSVs, and the name of the remapped value on the model (e.g.
    # accession.lesion_id).
    csv_field_name: str
    relation_name: str
    internal_id_name: str
    model: models.Model

    def internal_value(self, obj: models.Model) -> str:
        return getattr(getattr(obj, self.relation_name), self.internal_id_name)

    def external_value(self, obj: models.Model) -> str:
        return getattr(obj, self.csv_field_name)


class AccessionStatus(models.TextChoices):
    CREATING = "creating", "Creating"
    CREATED = "created", "Created"
    SKIPPED = "skipped", "Skipped"
    FAILED = "failed", "Failed"
    SUCCEEDED = "succeeded", "Succeeded"


class Accession(CreationSortedTimeStampedModel, AccessionMetadata):
    # the creator is either inherited from the zip creator, or directly attached in the
    # case of a single shot upload.
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="accessions")
    girder_id = models.CharField(blank=True, max_length=24, help_text="The image_id from Girder.")
    zip_upload = models.ForeignKey(
        ZipUpload,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="accessions",
    )
    cohort = models.ForeignKey(Cohort, on_delete=models.CASCADE, related_name="accessions")

    copyright_license = models.CharField(choices=CopyrightLicense.choices, max_length=255)

    # the original blob is stored in case blobs need to be reprocessed
    original_blob = S3FileField(unique=True)
    # the original blob name is stored and kept private in case of leaked data in filenames.
    original_blob_name = models.CharField(max_length=255, editable=False)
    original_blob_size = models.PositiveBigIntegerField(editable=False)

    # When instantiated, blob is empty, as it holds the EXIF-stripped image
    # this isn't unique because of the blank case, see constraints above.
    blob = S3FileField(blank=True)
    blob_name = models.CharField(max_length=255, editable=False, blank=True)
    # blob_size/width/height are nullable unless status is succeeded
    blob_size = models.PositiveBigIntegerField(null=True, blank=True, default=None, editable=False)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(
        choices=AccessionStatus.choices, max_length=20, default=AccessionStatus.CREATING
    )

    thumbnail_256 = S3FileField(blank=True)
    thumbnail_256_size = models.PositiveIntegerField(
        null=True, blank=True, default=None, editable=False
    )

    lesion = models.ForeignKey(
        Lesion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accessions",
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accessions",
    )
    rcm_case = models.ForeignKey(
        RcmCase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accessions",
    )

    objects = AccessionQuerySet.as_manager()

    class Meta(CreationSortedTimeStampedModel.Meta):
        # original_blob_name is unique at the *cohort* level, which also makes it unique at the zip
        # level.
        unique_together = [["cohort", "original_blob_name"]]

        constraints = [
            # girder_id should be unique among nonempty girder_id values
            UniqueConstraint(
                name="accession_unique_girder_id",
                fields=["girder_id"],
                condition=~Q(girder_id=""),
            ),
            # blob should be unique when it's filled out
            UniqueConstraint(name="accession_unique_blob", fields=["blob"], condition=~Q(blob="")),
            # blob_name should be unique when it's filled out
            UniqueConstraint(
                name="accession_unique_blob_name",
                fields=["blob_name"],
                condition=~Q(blob_name=""),
            ),
            # the original blob name should always be hidden, so blob_name shouldn't be the same
            CheckConstraint(
                name="accession_blob_name_not_original_blob_name",
                check=~Q(original_blob_name=F("blob_name")),
            ),
            # require blob_size / width / height for succeeded accessions
            CheckConstraint(
                name="accession_succeeded_blob_fields",
                check=Q(
                    status=AccessionStatus.SUCCEEDED,
                    thumbnail_256_size__isnull=False,
                    blob_size__isnull=False,
                    width__isnull=False,
                    height__isnull=False,
                )
                & ~Q(thumbnail_256="")
                & ~Q(blob_name="")
                | ~Q(status=AccessionStatus.SUCCEEDED),
            ),
            CheckConstraint(
                name="accession_concomitant_biopsy_diagnosis_confirm_type",
                check=Q(
                    concomitant_biopsy=True,
                    diagnosis_confirm_type="histopathology",
                )
                | ~Q(concomitant_biopsy=True),
            ),
            # identical lesion_id implies identical patient_id
            ExclusionConstraint(
                name="accession_lesion_id_patient_id_exclusion",
                expressions=[
                    ("lesion_id", "="),
                    ("patient_id", "<>"),
                ],
                condition=Q(lesion_id__isnull=False) & Q(patient_id__isnull=False),
            ),
            # identical rcm_case_id implies identical lesion_id
            ExclusionConstraint(
                name="accession_rcm_case_id_lesion_id_exclusion",
                expressions=[
                    ("rcm_case_id", "="),
                    ("lesion_id", "<>"),
                ],
                condition=Q(rcm_case_id__isnull=False) & Q(lesion_id__isnull=False),
            ),
            # each RCM case can only have at most one macroscopic image
            UniqueConstraint(
                name="accession_unique_rcm_case_id_macroscopic_image",
                fields=["cohort_id", "rcm_case_id"],
                condition=Q(image_type=ImageTypeEnum.rcm_macroscopic),
            ),
        ]

        indexes = [
            # useful for improving the performance of the cohort list page which needs per-cohort
            # lesion counts.
            models.Index(fields=["lesion_id", "id", "cohort_id"]),
            # useful for improving the performance of the cohort detail page which needs to provide
            # accession-wise status breakdowns.
            models.Index(fields=["cohort_id", "status", "created"]),
            # metadata selection does WHERE original_blob_name IN (...) queries
            models.Index(fields=["original_blob_name"]),
            models.Index(fields=["girder_id"]),
        ]

    def __str__(self) -> str:
        return self.blob_name

    remapped_internal_fields = [
        RemappedField("lesion_id", "lesion", "private_lesion_id", Lesion),
        RemappedField("patient_id", "patient", "private_patient_id", Patient),
        RemappedField("rcm_case_id", "rcm_case", "private_rcm_case_id", RcmCase),
    ]

    @property
    def published(self):
        return hasattr(self, "image")

    @property
    def reviewed(self):
        return hasattr(self, "review")

    @property
    def unreviewed(self):
        return not self.reviewed

    @property
    def metadata(self):
        ret = {}
        for field in self._meta.fields:
            if hasattr(AccessionMetadata, field.name) and getattr(self, field.name) is not None:
                ret[field.name] = getattr(self, field.name)
        return ret

    @staticmethod
    def metadata_keys():
        return [
            field.name for field in Accession._meta.fields if hasattr(AccessionMetadata, field.name)
        ]

    def generate_blob(self):
        """
        Generate `blob` and set `blob_size`, `height`, `width`.

        This is idempotent.
        The Accession will be saved and `status` will be updated appropriately.
        """
        try:
            with self.original_blob.open("rb") as original_blob_stream:
                blob_mime_type = guess_mime_type(original_blob_stream, self.original_blob_name)
            blob_major_mime_type = blob_mime_type.partition("/")[0]
            if blob_major_mime_type != "image":
                raise InvalidBlobError(  # noqa: TRY301
                    f'Blob has a non-image MIME type: "{blob_mime_type}"'
                )

            # Set a larger max size, to accommodate confocal images
            # This uses ~1.1GB of memory
            PIL.Image.MAX_IMAGE_PIXELS = 20_000 * 20_000 * 3
            try:
                img = PIL.Image.open(original_blob_stream)
            except PIL.Image.UnidentifiedImageError as e:
                raise InvalidBlobError("Blob cannot be recognized by PIL.") from e

            # Explicitly load the image, so any decoding errors can be caught
            try:
                img.load()
            except OSError as e:
                if "image file is truncated" in str(e):
                    raise InvalidBlobError("Blob appears truncated.") from e

                # Any other errors are not expected, so re-raise them natively
                raise

            # Strip any alpha channel
            img = img.convert("RGB")

            with tempfile.SpooledTemporaryFile() as stripped_blob_stream:
                img.save(stripped_blob_stream, format="JPEG")

                stripped_blob_stream.seek(0, io.SEEK_END)
                stripped_blob_size = stripped_blob_stream.tell()
                stripped_blob_stream.seek(0)

                self.blob_name = f"{uuid4()}.jpg"
                self.blob = InMemoryUploadedFile(
                    file=stripped_blob_stream,
                    field_name=None,
                    name=self.blob_name,
                    content_type="image/jpeg",
                    size=stripped_blob_size,
                    charset=None,
                )
                self.blob_size = stripped_blob_size
                self.height = img.height
                self.width = img.width

                self.save(update_fields=["blob_name", "blob", "blob_size", "height", "width"])

            self.generate_thumbnail()

        except InvalidBlobError:
            logger.exception("Marking accession %d as skipped due to invalid blob", self.pk)
            self.status = AccessionStatus.SKIPPED
            self.save(update_fields=["status"])
            # Expected failure, so return cleanly
        except Exception:
            logger.exception("Marking accession %d as failed due to unexpected error", self.pk)
            self.status = AccessionStatus.FAILED
            self.save(update_fields=["status"])
            # Unexpected failure, so re-raise
            raise
        else:
            self.status = AccessionStatus.SUCCEEDED
            self.save(update_fields=["status"])

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
            img.save(thumbnail_stream, format="JPEG", quality=75, optimize=True)
            thumbnail_stream.seek(0)

            self.thumbnail_256_size = thumbnail_stream.getbuffer().nbytes
            self.thumbnail_256 = InMemoryUploadedFile(
                file=thumbnail_stream,
                field_name=None,
                name=(
                    f"{self.image.isic_id}_thumbnail_256.jpg"
                    if hasattr(self, "image")
                    else "thumbnail_256.jpg"
                ),
                content_type="image/jpeg",
                size=self.thumbnail_256_size,
                charset=None,
            )
            self.save(update_fields=["thumbnail_256", "thumbnail_256_size"])

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
        return self._age_approx(self.metadata["age"]) if "age" in self.metadata else None

    def _require_unpublished(self):
        if self.published:
            raise ValidationError("Can't modify the accession as it's already been published.")

    def update_metadata(  # noqa: C901
        self, user: User, csv_row: dict, *, ignore_image_check=False, reset_review=True
    ) -> bool:
        """
        Apply metadata to an accession from a row in a CSV.

        ALL metadata modifications must go through update_metadata since it:
        1) Checks to see if the accession can be modified
        2) Manages audit trails (MetadataVersion records)
        3) Resets the review
        4) Manages remapping internal fields
        """
        if self.pk and not ignore_image_check:
            self._require_unpublished()

        def maybe_remap_internal_metadata(metadata: dict) -> bool:
            mapped = False

            for field in self.remapped_internal_fields:
                parsed_field = metadata.get(field.csv_field_name)

                if parsed_field and (
                    not getattr(self, field.relation_name)
                    or field.internal_value(self) != parsed_field
                ):
                    mapped = True
                    value, _ = field.model.objects.get_or_create(
                        cohort=self.cohort, **{field.internal_id_name: parsed_field}
                    )
                    setattr(self, field.relation_name, value)

            return mapped

        with transaction.atomic():
            modified = False

            # keep original copy so we only modify metadata if it changes
            original_metadata = deepcopy(self.metadata)
            # create second copy to avoid mutating self.metadata unless it will be changed
            metadata = deepcopy(self.metadata)
            # merge metadata with existing metadata, this is necessary for metadata
            # that has interdependent checks.
            metadata.update(csv_row)
            parsed_metadata = MetadataRow.model_validate(metadata)

            # update unstructured metadata
            if (
                parsed_metadata.unstructured
                and self.unstructured_metadata.value != parsed_metadata.unstructured
            ):
                modified = True
                self.unstructured_metadata.value.update(parsed_metadata.unstructured)

            # update structured metadata
            new_metadata = parsed_metadata.model_dump(
                exclude_unset=True, exclude_none=True, exclude={"unstructured"}
            )
            new_remapped_internal_metadata = maybe_remap_internal_metadata(new_metadata)

            # remapped metadata has already been captured, so strip it to prevent it from
            # being added to the metadata and exposing the internal values.
            for field in self.remapped_internal_fields:
                if field.csv_field_name in new_metadata:
                    del new_metadata[field.csv_field_name]

            if (
                new_metadata and original_metadata != new_metadata
            ) or new_remapped_internal_metadata:
                modified = True

                for k, v in new_metadata.items():
                    setattr(self, k, v)

                if reset_review:
                    # if a new metadata item has been added or an existing has been modified,
                    # reset the review state.
                    from isic.ingest.services.accession.review import (
                        accession_review_delete,
                    )

                    accession_review_delete(accession=self)

            if modified:
                remapped_internal_values = {}
                for field in self.remapped_internal_fields:
                    remapped_internal_values.setdefault(field.relation_name, {})

                    if getattr(self, field.relation_name):
                        remapped_internal_values[field.relation_name] = {
                            "internal": field.internal_value(self),
                            "external": field.external_value(self),
                        }

                self.metadata_versions.create(
                    creator=user,
                    metadata=self.metadata,
                    unstructured_metadata=self.unstructured_metadata.value,
                    **remapped_internal_values,
                )
                self.unstructured_metadata.save()
                self.save()

        return modified

    def remove_metadata(
        self,
        user: User,
        metadata_fields: list[str],
        *,
        ignore_image_check=False,
        reset_review=True,
    ):
        """Remove metadata from an accession."""
        if self.pk and not ignore_image_check:
            self._require_unpublished()

        modified = False
        with transaction.atomic():
            for field in metadata_fields:
                if getattr(self, field) is not None:
                    setattr(self, field, None)

                    modified = True

                    if reset_review:
                        from isic.ingest.services.accession.review import (
                            accession_review_delete,
                        )

                        accession_review_delete(accession=self)

            if modified:
                self.metadata_versions.create(
                    creator=user,
                    metadata=self.metadata,
                    unstructured_metadata=self.unstructured_metadata.value,
                )
                self.save()

    def remove_unstructured_metadata(
        self, user: User, unstructured_metadata_fields: list[str]
    ) -> bool:
        """Remove unstructured metadata from an accession."""
        modified = False
        with transaction.atomic():
            for field in unstructured_metadata_fields:
                if self.unstructured_metadata.value.pop(field, None) is not None:
                    modified = True

            if modified:
                self.metadata_versions.create(
                    creator=user,
                    metadata=self.metadata,
                    unstructured_metadata=self.unstructured_metadata.value,
                )
                self.unstructured_metadata.save()

        return modified

    def full_clean(self, *args, **kwargs):
        if (
            "unstructured_metadata"
            not in kwargs.get("exclude", {}).get("unstructured_metadata", [])
            and not self.unstructured_metadata
        ):
            raise Exception("unstructured_metadata is required")

        super().full_clean(*args, **kwargs)
