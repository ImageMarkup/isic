from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel


def doi_upload_to(instance: "Doi", filename: str) -> str:
    return f"doi-bundles/{instance.slug}/{filename}"


class Doi(TimeStampedModel):
    class Meta:
        verbose_name = "DOI"
        verbose_name_plural = "DOIs"

    id = models.CharField(
        max_length=30, primary_key=True, validators=[RegexValidator(r"^\d+\.\d+/\d+$")]
    )
    slug = models.SlugField(max_length=150, unique=True)
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)

    url = models.CharField(max_length=200)

    bundle = models.FileField(upload_to=doi_upload_to, null=True, blank=True)
    bundle_size = models.PositiveBigIntegerField(null=True, blank=True)

    metadata = models.FileField(upload_to=doi_upload_to, null=True, blank=True)
    metadata_size = models.PositiveIntegerField(null=True, blank=True)

    citations = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return self.id

    def get_absolute_url(self):
        return reverse("core/doi-detail", kwargs={"slug": self.slug})
