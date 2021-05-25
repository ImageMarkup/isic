from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .image import Image


class Collection(TimeStampedModel):
    images = models.ManyToManyField(Image, related_name='collections')

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('core/collection-detail', args=[self.pk])
