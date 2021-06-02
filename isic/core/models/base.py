from django.db import models
from django_extensions.db.fields import CreationDateTimeField
from django_extensions.db.models import TimeStampedModel


class CreationSortedTimeStampedModel(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        abstract = True
        ordering = ['-created']
        get_latest_by = 'created'

    created = CreationDateTimeField(db_index=True)


class CopyrightLicense(models.TextChoices):
    CC_0 = 'CC-0', 'CC-0'

    # These 2 require attribution
    CC_BY = 'CC-BY', 'CC-BY'
    CC_BY_NC = 'CC-BY-NC', 'CC-BY-NC'
