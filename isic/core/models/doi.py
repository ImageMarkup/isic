from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django_extensions.db.models import TimeStampedModel


class Doi(TimeStampedModel):
    id = models.CharField(
        max_length=30, primary_key=True, validators=[RegexValidator(r"^\d+\.\d+/\d+$")]
    )
    slug = models.SlugField(max_length=150, unique=True)
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)

    url = models.CharField(max_length=200)

    bundle = models.FileField(upload_to="doi-bundles/", null=True, blank=True)
    bundle_size = models.PositiveBigIntegerField(null=True, blank=True)

    citations = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.id
