import json
import random

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.core.validators import RegexValidator, URLValidator
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


class AbstractDoi(TimeStampedModel):
    class Meta:
        abstract = True

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


class Doi(AbstractDoi):
    class Meta:
        verbose_name = "DOI"
        verbose_name_plural = "DOIs"


class DraftDoi(AbstractDoi):
    class Meta:
        verbose_name = "Draft DOI"
        verbose_name_plural = "Draft DOIs"


# https://datacite-metadata-schema.readthedocs.io/en/4.6/appendices/appendix-1/relationType/
class RelationType(models.TextChoices):
    IS_REFERENCED_BY = "IsReferencedBy", "Is Referenced By"
    IS_SUPPLEMENTED_BY = "IsSupplementedBy", "Is Supplemented By"
    IS_DESCRIBED_BY = "IsDescribedBy", "Is Described By"


# https://datacite-metadata-schema.readthedocs.io/en/4.6/properties/relatedidentifier/#a-relatedidentifiertype
class RelatedIdentifierType(models.TextChoices):
    DOI = "DOI", "DOI"
    URL = "URL", "URL"


class AbstractDoiRelatedIdentifier(models.Model):
    relation_type = models.CharField(
        max_length=20,
        choices=RelationType.choices,
    )
    related_identifier_type = models.CharField(
        max_length=10,
        choices=RelatedIdentifierType.choices,
    )
    related_identifier = models.CharField(max_length=500)

    class Meta:
        abstract = True

        unique_together = [
            ["doi", "relation_type", "related_identifier_type", "related_identifier"]
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["doi"],
                condition=models.Q(relation_type="IsDescribedBy"),
                name="%(class)s_unique_isdescribedby_per_doi",
            )
        ]

    def __str__(self) -> str:
        return f"{self.doi.id} - {self.get_relation_type_display()}: {self.related_identifier}"

    def clean(self):
        if self.relation_type not in RelationType.values:
            raise ValidationError(f"Invalid relation type: {self.relation_type}")

        if self.related_identifier_type not in RelatedIdentifierType.values:
            raise ValidationError(f"Invalid identifier type: {self.related_identifier_type}")

        if self.related_identifier_type == RelatedIdentifierType.DOI:
            doi_validator = RegexValidator(
                regex=r"^10\.\d+/.*$",
                message="Enter a valid DOI format (e.g., 10.1000/182).",
            )
            doi_validator(self.related_identifier)
        elif self.related_identifier_type == RelatedIdentifierType.URL:
            url_validator = URLValidator()
            url_validator(self.related_identifier)

        if self.relation_type == RelationType.IS_DESCRIBED_BY and self.doi_id:
            model_class = self.__class__
            existing_query = model_class.objects.filter(
                doi=self.doi, relation_type=RelationType.IS_DESCRIBED_BY
            )
            if self.pk:
                existing_query = existing_query.exclude(pk=self.pk)

            if existing_query.exists():
                raise ValidationError("Only one 'Is Described By' relation is allowed per DOI.")

    @classmethod
    def validate_related_identifiers(cls, related_identifiers_data):
        for data in related_identifiers_data:
            instance = cls(
                doi=None,
                relation_type=data["relation_type"],
                related_identifier_type=data["related_identifier_type"],
                related_identifier=data["related_identifier"],
            )
            try:
                instance.clean()
            except ValidationError as e:
                raise ValueError(str(e)) from e


class DoiRelatedIdentifier(AbstractDoiRelatedIdentifier):
    doi = models.ForeignKey(Doi, on_delete=models.CASCADE, related_name="related_identifiers")


class DraftDoiRelatedIdentifier(AbstractDoiRelatedIdentifier):
    doi = models.ForeignKey(DraftDoi, on_delete=models.CASCADE, related_name="related_identifiers")
