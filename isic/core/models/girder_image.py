from bson import ObjectId
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q

from isic.core.models.isic_id import IsicId
from isic.ingest.models import Accession
from isic.login.girder import get_girder_db


class GirderImageStatus(models.TextChoices):
    UNKNOWN = 'unknown', 'Unknown'
    CORRUPT = 'corrupt', 'Corrupt'
    MIGRATED = 'migrated', 'Migrated'
    TRUE_DUPLICATE = 'true_duplicate', 'True Duplicate'


class GirderDataset(models.Model):
    id = models.CharField(
        primary_key=True,
        max_length=24,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    name = models.CharField(max_length=255)
    public = models.BooleanField()

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
        # If status is not unknown, must have accession_id
        constraints = [
            models.CheckConstraint(
                name='non_unknown_have_accession_id',
                check=Q(status=GirderImageStatus.UNKNOWN) | Q(accession_id__isnull=False),
            ),
        ]

    status = models.CharField(
        choices=GirderImageStatus.choices, default=GirderImageStatus.UNKNOWN, max_length=30
    )

    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(IsicId, on_delete=models.PROTECT, editable=False)
    item_id = models.CharField(
        unique=True,
        max_length=24,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    file_id = models.CharField(
        unique=True,
        max_length=24,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )

    dataset = models.ForeignKey(GirderDataset, on_delete=models.PROTECT)

    original_filename = models.CharField(max_length=255)
    original_file_relpath = models.CharField(max_length=255, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    unstructured_metadata = models.JSONField(default=dict, blank=True)

    original_blob_dm = models.CharField(
        max_length=64,
        validators=[RegexValidator(r'^[0-9a-f]{64}$')],
    )
    # stripped_blob_dm should match Django
    stripped_blob_dm = models.CharField(
        max_length=64,
        validators=[RegexValidator(r'^[0-9a-f]{64}$')],
    )

    accession_id = models.ForeignKey(Accession, null=True, blank=True, on_delete=models.CASCADE)
