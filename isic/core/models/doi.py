import json
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import storages
from django.core.validators import RegexValidator
from django.db import models
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .collection import Collection


def doi_upload_to(instance: "Doi", filename: str) -> str:
    return f"dois/{instance.id.replace('/', '-')}/{filename}"


def doi_storage():
    return storages["sponsored"]


def _generate_random_doi_id():
    # pad DOI with leading zeros so all DOIs are prefix/6 digits
    return f"{settings.ISIC_DATACITE_DOI_PREFIX}/{random.randint(10_000, 999_999):06}"  # noqa: S311


class Doi(TimeStampedModel):
    class Meta:
        verbose_name = "DOI"
        verbose_name_plural = "DOIs"

    id = models.CharField(
        max_length=30,
        primary_key=True,
        default=_generate_random_doi_id,
        validators=[RegexValidator(r"^\d+\.\d+/\d+$")],
    )
    slug = models.SlugField(max_length=150, unique=True)
    collection = models.OneToOneField(Collection, on_delete=models.PROTECT)
    creator = models.ForeignKey(User, on_delete=models.RESTRICT)

    bundle = models.FileField(upload_to=doi_upload_to, storage=doi_storage, null=True, blank=True)
    bundle_size = models.PositiveBigIntegerField(null=True, blank=True)

    metadata = models.FileField(upload_to=doi_upload_to, storage=doi_storage, null=True, blank=True)
    metadata_size = models.PositiveIntegerField(null=True, blank=True)

    citations = models.JSONField(default=dict, blank=True)
    schema_org_dataset = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return self.id

    @property
    def external_url(self) -> str:
        return f"https://doi.org/{self.id}"

    def get_absolute_url(self) -> str:
        return reverse("core/doi-detail", kwargs={"slug": self.slug})

    def get_schema_org_dataset_json(self):
        return json.dumps(self.schema_org_dataset)
