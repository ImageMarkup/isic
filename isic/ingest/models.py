from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django_extensions.db.models import TimeStampedModel
from s3_file_field import S3FileField


class Cohort(TimeStampedModel):
    girder_id = models.CharField(blank=True, max_length=24, help_text='The dataset_id from Girder.')

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name

    # @property
    # def is_complete(self):
    #     if self.status == Zip.Status.CREATED:
    #         return False
    #     elif self.status == Zip.Status.COMPLETED:
    #         return True
    #     else:
    #         return self.blobs.filter(completed__isnull=True).count() == 0
    #
    # @property
    # def num_failed_images(self):
    #     return self.records.filter(succeeded=False).count()


class Zip(TimeStampedModel):
    class Status(models.TextChoices):
        CREATED = 'created', 'Created'
        STARTED = 'extracting', 'Extracting'
        COMPLETED = 'extracted', 'Extracted'

    # creator = models.ForeignKey(User, on_delete=models.PROTECT)
    # status = models.CharField(
    #     max_length=10, choices=Status.choices, default=Status.CREATED
    # )
    girder_id = models.CharField(blank=True, max_length=24, help_text='The batch_id from Girder.')

    cohort = models.ForeignKey(Cohort, null=True, on_delete=models.CASCADE, related_name='zips')

    blob = S3FileField(blank=True)
    blob_name = models.CharField(blank=True, max_length=255)
    blob_size = models.PositiveBigIntegerField(null=True)

    def __str__(self) -> str:
        return self.blob_name

    def get_absolute_url(self):
        return reverse('zip-detail', args=[self.id])

    # def reset(self):
    #     # warning - deletes all annotations/images/and records
    #     with transaction.atomic():
    #         # TODO: delete the images?
    #         self.blobs.all().delete()
    #         self.last_updated = self.created
    #         self.status = UploadStatus.CREATED
    #         self.save(update_fields=['last_updated', 'status'])


# class UploadBlob(TimeStampedModel):
#     upload = models.ForeignKey(Zip, related_name='blobs', on_delete=models.CASCADE)
#     blob_name = models.CharField(max_length=255)
#     blob = S3FileField()
#
#     completed = models.DateTimeField(blank=True, null=True)
#     succeeded = models.BooleanField(blank=True, null=True)
#     fail_reason = models.TextField(blank=True, null=True)
#
#     def reset(self):
#         from isic.studies.models import Image
#
#         with transaction.atomic():
#             try:
#                 self.image.delete()
#             except Image.DoesNotExist:
#                 pass
#
#             self.completed = None
#             self.succeeded = None
#             self.fail_reason = None
#             self.upload.status = UploadStatus.STARTED
#             self.upload.save(update_fields=['status'])
#             self.save()
#
#     def get_status_display(self):
#         if not self.completed:
#             return 'Pending'
#         elif self.succeeded:
#             return 'Succeeded'
#         else:
#             return 'Failed'
#
#
#     def is_stuck(self, threshold=120):
#         threshold = timedelta(threshold)
#
#         if self.status == UploadStatus.COMPLETED:
#             return False
#
#         age: timedelta = timezone.now() - self.last_updated
#         return age > threshold
#
#
#     def succeed(self):
#         self.upload.last_updated = timezone.now()
#         self.completed = timezone.now()
#         self.succeeded = True
#         self.save(update_fields=['completed', 'succeeded'])
#         self.upload.save(update_fields=['last_updated'])
#
#     def fail(self, reason=None):
#         self.upload.last_updated = timezone.now()
#         self.completed = timezone.now()
#         self.succeeded = False
#
#         if reason:
#             self.fail_reason = reason
#
#         self.save(update_fields=['completed', 'succeeded', 'fail_reason'])
#         self.upload.save(update_fields=['last_updated'])
