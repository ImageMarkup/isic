from django.core.validators import RegexValidator
from django.db import models
from django.db.models import JSONField
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from isic.core.fields import IsicIdField


class DuplicateImage(TimeStampedModel):
    accession = models.ForeignKey(
        'ingest.Accession', on_delete=models.CASCADE, related_name='duplicates'
    )
    girder_id = models.CharField(
        max_length=24,
        unique=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    isic_id = IsicIdField()
    metadata = JSONField(default=dict)


class ImageRedirect(TimeStampedModel):
    isic_id = IsicIdField()
    image = models.ForeignKey('Image', on_delete=models.PROTECT, related_name='redirects')


class Image(TimeStampedModel):
    accession = models.OneToOneField(
        'ingest.Accession',
        on_delete=models.PROTECT,
    )
    isic_id = IsicIdField()

    public = models.BooleanField(default=False)

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse('core/image-detail', args=[self.pk])


class Collection(TimeStampedModel):
    images = models.ManyToManyField(Image)

    # TODO: probably make it unique per user, or unique for official collections
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name
