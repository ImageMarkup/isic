from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel


class Doi(TimeStampedModel):
    # TODO: figure out which fields to store here
    id = models.CharField(
        max_length=30, primary_key=True, validators=[RegexValidator(r'^\d+\.\d+/\d+$')]
    )
    url = models.CharField(max_length=200)
