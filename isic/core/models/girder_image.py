from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from isic.core.constants import MONGO_ID_REGEX
from isic.core.models.isic_id import IsicId
from isic.ingest.models import Accession


class GirderImageStatus(models.TextChoices):
    UNKNOWN = "unknown", "Unknown"
    NON_IMAGE = "non_image", "Non-Image"
    CORRUPT = "corrupt", "Corrupt"
    MIGRATED = "migrated", "Migrated"
    TRUE_DUPLICATE = "true_duplicate", "True Duplicate"


class GirderDataset(models.Model):
    id = models.CharField(
        primary_key=True,
        max_length=24,
        validators=[RegexValidator(f"^{MONGO_ID_REGEX}$")],
    )
    name = models.CharField(max_length=255)
    public = models.BooleanField()

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class GirderImage(models.Model):
    status = models.CharField(
        choices=GirderImageStatus.choices,
        default=GirderImageStatus.UNKNOWN,
        max_length=30,
    )
    pre_review = models.BooleanField(null=True)

    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    item_id = models.CharField(
        db_index=True,
        unique=True,
        max_length=24,
        validators=[RegexValidator(f"^{MONGO_ID_REGEX}$")],
        editable=False,
    )
    file_id = models.CharField(
        unique=True,
        max_length=24,
        validators=[RegexValidator(f"^{MONGO_ID_REGEX}$")],
        editable=False,
    )

    dataset = models.ForeignKey(
        GirderDataset, on_delete=models.PROTECT, related_name="images", editable=False
    )

    original_filename = models.CharField(max_length=255, editable=False)
    original_file_relpath = models.CharField(max_length=255, blank=True, editable=False)

    metadata = models.JSONField(default=dict, blank=True, editable=False)
    unstructured_metadata = models.JSONField(default=dict, blank=True, editable=False)

    original_blob_dm = models.CharField(
        max_length=64, validators=[RegexValidator(r"^[0-9a-f]{64}$")], editable=False
    )
    # stripped_blob_dm should match Django
    stripped_blob_dm = models.CharField(
        max_length=64,
        validators=[RegexValidator(r"^[0-9a-f]{64}$")],
        blank=True,
        editable=False,
    )

    accession = models.OneToOneField(
        Accession, null=True, blank=True, on_delete=models.CASCADE, editable=False
    )

    raw = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["item_id"]
        # If status is not unknown, must have accession
        constraints = [
            models.CheckConstraint(
                name="non_unknown_have_accession",
                condition=Q(status=GirderImageStatus.UNKNOWN)
                | Q(status=GirderImageStatus.NON_IMAGE)
                | Q(accession__isnull=False),
            ),
            models.CheckConstraint(
                name="non_non_image_have_stripped_blob_dm",
                condition=Q(status=GirderImageStatus.NON_IMAGE) | ~Q(stripped_blob_dm=""),
            ),
        ]

    def __str__(self) -> str:
        return self.isic_id
