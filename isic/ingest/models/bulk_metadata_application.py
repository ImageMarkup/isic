from django.contrib.auth.models import User
from django.db import models


class BulkMetadataApplication(models.Model):
    """
    Stores a record of a user's application of metadata to some set of images.

    This is used to track the an application of metadata to a set of images with an
    optional message to dictate why this metadata is being applied. It can optionally point
    to a MetadataFile.
    """

    created = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    metadata_file = models.ForeignKey(
        "MetadataFile",
        # allow users to delete metadata files while keeping a record of the application
        on_delete=models.SET_NULL,
        related_name="metadata_applications",
        null=True,
        blank=True,
    )
    message = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.message
