from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.expressions import F
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.core.models import Image

from .study import Study
from .study_task import StudyTask


class Annotation(TimeStampedModel):
    class Meta:
        constraints = [
            CheckConstraint(
                name="annotation_start_time_check",
                condition=Q(start_time__lte=F("created")),
            ),
        ]
        unique_together = [["study", "task", "image", "annotator"]]

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="annotations")
    image = models.ForeignKey(Image, on_delete=models.PROTECT)
    annotator = models.ForeignKey(User, on_delete=models.PROTECT)
    task = models.OneToOneField(StudyTask, related_name="annotation", on_delete=models.RESTRICT)

    # For the ISIC GUI this time is generated on page load.
    # The created field acts as the end_time value.
    # This is nullable in the event that third party apps submit annotations, but
    # all annotations created by this app submit a start_time.
    start_time = models.DateTimeField(null=True)

    def get_absolute_url(self) -> str:
        return reverse("annotation-detail", args=[self.pk])

    @property
    def annotation_duration(self) -> timedelta | None:
        if self.start_time:
            return self.created - self.start_time
        return None
