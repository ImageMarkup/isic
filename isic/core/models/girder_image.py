from bson import ObjectId
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from isic.core.models.isic_id import IsicId
from isic.ingest.models import Accession
from isic.login.girder import get_girder_db


class GirderImageStatus(models.TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    NON_IMAGE = 'non_image', 'Non-Image'
    CORRUPT = 'corrupt', 'Corrupt'
    MIGRATED = 'migrated', 'Migrated'
    TRUE_DUPLICATE = 'true_duplicate', 'True Duplicate'


class GirderDataset(models.Model):
    class Meta:
        ordering = ['id']

    id = models.CharField(
        primary_key=True,
        max_length=24,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    name = models.CharField(max_length=255)
    public = models.BooleanField()

    def __str__(self) -> str:
        return self.name

    @classmethod
    def get_or_create(cls, dataset_id: str):
        girder_db = get_girder_db()

        dataset = girder_db['dataset'].find_one({'_id': ObjectId(dataset_id)})
        if not dataset:
            raise Exception(f'Could not find dataset_id: {dataset_id}')

        return cls.objects.get_or_create(
            id=str(dataset['_id']), defaults={'name': dataset['name'], 'public': dataset['public']}
        )[0]


class GirderImage(models.Model):
    class Meta:
        ordering = ['item_id']
        # If status is not unknown, must have accession
        constraints = [
            models.CheckConstraint(
                name='non_unknown_have_accession',
                check=Q(status=GirderImageStatus.UNKNOWN)
                | Q(status=GirderImageStatus.NON_IMAGE)
                | Q(accession__isnull=False),
            ),
            models.CheckConstraint(
                name='non_non_image_have_stripped_blob_dm',
                check=Q(status=GirderImageStatus.NON_IMAGE) | ~Q(stripped_blob_dm=''),
            ),
        ]

    status = models.CharField(
        choices=GirderImageStatus.choices, default=GirderImageStatus.UNKNOWN, max_length=30
    )

    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    item_id = models.CharField(
        db_index=True,
        unique=True,
        max_length=24,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
        editable=False,
    )
    file_id = models.CharField(
        unique=True, max_length=24, validators=[RegexValidator(r'^[0-9a-f]{24}$')], editable=False
    )

    dataset = models.ForeignKey(
        GirderDataset, on_delete=models.PROTECT, related_name='images', editable=False
    )

    original_filename = models.CharField(max_length=255, editable=False)
    original_file_relpath = models.CharField(max_length=255, blank=True, editable=False)

    metadata = models.JSONField(default=dict, blank=True, editable=False)
    unstructured_metadata = models.JSONField(default=dict, blank=True, editable=False)

    original_blob_dm = models.CharField(
        max_length=64, validators=[RegexValidator(r'^[0-9a-f]{64}$')], editable=False
    )
    # stripped_blob_dm should match Django
    stripped_blob_dm = models.CharField(
        max_length=64, validators=[RegexValidator(r'^[0-9a-f]{64}$')], blank=True, editable=False
    )

    accession = models.ForeignKey(
        Accession, null=True, blank=True, on_delete=models.CASCADE, editable=False
    )

    def __str__(self) -> str:
        return self.isic_id
