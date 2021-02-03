from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.urls.base import reverse
from django_extensions.db.models import TimeStampedModel
from s3_file_field import S3FileField


class Cohort(TimeStampedModel):
    creator = models.ForeignKey(User, null=True, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text='The dataset_id from Girder.')

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

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

    class ReviewStatus(models.TextChoices):
        REJECTED = 'rejected', 'Rejected'
        ACCEPTED = 'accepted', 'Accepted'

    class RejectReason(models.TextChoices):
        LOW_QUALITY = 'low_quality', 'Low Quality'
        DUPLICATE = 'duplicate', 'Duplicate'
        HAS_PHI = 'has_phi', 'Has PHI'

    class Meta:
        # A blob_name is unique at the *cohort* level, but that's not possible to enforce at the
        # database layer. At least enforce the blob_name being unique at the zip level.
        # TODO: How to properly enforce cohort, blob_name uniqueness at the app layer.
        unique_together = [['upload', 'blob_name']]

    upload = models.ForeignKey('Zip', on_delete=models.CASCADE, related_name='accessions')

    blob = S3FileField()
    blob_name = models.CharField(max_length=255, db_index=True)
    blob_size = models.PositiveBigIntegerField()

    status = models.CharField(choices=Status.choices, max_length=20, default=Status.CREATING)
    review_status = models.CharField(
        choices=ReviewStatus.choices, max_length=20, null=True, blank=True
    )
    reject_reason = models.CharField(
        choices=RejectReason.choices, max_length=20, null=True, blank=True
    )

    metadata = JSONField(default=dict)
    unstructured_metadata = JSONField(default=dict)


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

    def succeed(self):
        self.status = Zip.Status.COMPLETED
        self.save(update_fields=['status'])

    def reset(self):
        with transaction.atomic():
            self.accessions.all().delete()
            self.status = Zip.Status.CREATED
            self.save(update_fields=['status'])
