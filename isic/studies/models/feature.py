from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django_extensions.db.models import TimeStampedModel

from .annotation import Annotation
from .study import Study


class Feature(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        ordering = ["name"]

    required = models.BooleanField(default=False)
    name = ArrayField(models.CharField(max_length=200))
    official = models.BooleanField()

    @property
    def label(self) -> str:
        return " : ".join(self.name)

    def __str__(self) -> str:
        return self.label

    def save(self, **kwargs):
        if (
            self.pk
            and Annotation.objects.filter(study__in=Study.objects.filter(features=self)).exists()
        ):
            raise ValidationError("Can't modify the feature, someone has already annotated it.")

        return super().save(**kwargs)
