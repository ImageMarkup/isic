from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.expressions import F
from django.db.models.functions import Upper
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from pgvector.django import HalfVectorField

from isic.core.dsl import django_parser, parse_query
from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId


class ImageQuerySet(models.QuerySet["Image"]):
    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)

    def from_search_query(self, query: str):
        if query == "":
            return self
        return self.filter(parse_query(django_parser, query) or Q())


class ImageManager(models.Manager["Image"]):
    def get_queryset(self) -> ImageQuerySet:
        return ImageQuerySet(self.model, using=self._db).defer("embedding")

    def with_elasticsearch_properties(self):
        return self.select_related("accession__cohort").annotate(
            coll_pks=ArrayAgg("collections", distinct=True, default=[]),
            contributor_owner_ids=ArrayAgg(
                "accession__cohort__contributor__owners", distinct=True, default=[]
            ),
            shared_to=ArrayAgg(
                "shares",
                # confusingly, this filters out where shares__grantee_id is None so
                # we don't end up with [null] in elasticsearch.
                # see also https://stackoverflow.com/questions/55098215/exclude-null-values-from-djangos-arrayagg
                filter=~Q(shares=None),
                distinct=True,
                default=[],
            ),
        )

    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)


class Image(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        ordering = ["created"]

        indexes = [
            # icontains uses Upper(name) for searching
            GinIndex(OpClass(Upper("isic"), name="gin_trgm_ops"), name="isic_name_gin")
        ]
        constraints = [
            CheckConstraint(
                name="image_embedding_public_check",
                condition=Q(embedding__isnull=True) | Q(public=True),
            ),
        ]

    accession = models.OneToOneField(
        Accession,
        on_delete=models.PROTECT,
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(
        IsicId,
        on_delete=models.PROTECT,
        editable=False,
        verbose_name="isic id",
    )
    # The creator is the person who published the accessions.
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="published_images")

    # index is used because public is filtered in every permissions check
    public = models.BooleanField(default=False, db_index=True)

    shares = models.ManyToManyField(User, through="ImageShare", through_fields=("image", "grantee"))

    embedding = HalfVectorField(dimensions=3584, null=True, blank=True)

    objects = ImageManager()

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse("core/image-detail", args=[self.isic_id])

    @property
    def blob(self):
        if self.public:
            return self.accession.sponsored_blob
        return self.accession.blob

    @property
    def thumbnail_256(self):
        if self.public:
            return self.accession.sponsored_thumbnail_256_blob
        return self.accession.thumbnail_256

    @property
    def extension(self) -> str:
        return PurePosixPath(self.blob.file.name).suffix.lstrip(".")

    @property
    def has_patient(self) -> bool:
        return self.accession.patient_id is not None

    @property
    def has_lesion(self) -> bool:
        return self.accession.lesion_id is not None

    @property
    def has_rcm_case(self) -> bool:
        return self.accession.rcm_case_id is not None

    @property
    def has_embedding(self) -> bool:
        return self.embedding is not None

    @property
    def metadata(self) -> dict:
        """
        Return the metadata for an image.

        Note that the metadata for the image is sanitized unlike the metadata for the accession
        which is behind the "firewall" of ingest. This includes rounded ages and remapped IDs.
        """
        image_metadata = deepcopy(self.accession.metadata)

        for computed_field in Accession.computed_fields:
            if computed_field.input_field_name in image_metadata:
                computed_output_fields = computed_field.transformer(
                    image_metadata[computed_field.input_field_name]
                )

                if computed_output_fields:
                    image_metadata.update(computed_output_fields)

                del image_metadata[computed_field.input_field_name]

        for remapped_field in Accession.remapped_internal_fields:
            if getattr(self.accession, remapped_field.csv_field_name) is not None:
                image_metadata[remapped_field.csv_field_name] = getattr(
                    self.accession, remapped_field.csv_field_name
                )

        return image_metadata

    def to_elasticsearch_document(self, *, body_only=False) -> dict:
        # Can only be called on images that were fetched with with_elasticsearch_properties.
        document = {
            "id": self.pk,
            "created": self.created,
            "isic_id": self.isic_id,
            "public": self.public,
            "copyright_license": self.accession.copyright_license,
            "blob_size": self.accession.blob_size,
            # TODO: make sure these fields can't be searched on
            "contributor_owner_ids": self.contributor_owner_ids,
            "shared_to": self.shared_to,
            "collections": self.coll_pks,
        }

        document.update(self.metadata)

        if body_only:
            return document

        # index the document by image.pk so it can be updated later.
        return {"_id": self.pk, "_source": document}

    def same_patient_images(self) -> QuerySet[Image]:
        if not self.has_patient:
            return Image.objects.none()

        return (
            Image.objects.filter(accession__cohort_id=self.accession.cohort_id)
            .filter(accession__patient_id=self.accession.patient_id)
            .exclude(pk=self.pk)
        )

    def same_lesion_images(self) -> QuerySet[Image]:
        if not self.has_lesion:
            return Image.objects.none()

        return (
            Image.objects.filter(accession__cohort_id=self.accession.cohort_id)
            .filter(accession__lesion_id=self.accession.lesion_id)
            .exclude(pk=self.pk)
        )

    def same_rcm_case_images(self) -> QuerySet[Image]:
        if not self.has_rcm_case:
            return Image.objects.none()

        return (
            Image.objects.filter(accession__cohort_id=self.accession.cohort_id)
            .filter(accession__rcm_case_id=self.accession.rcm_case_id)
            .exclude(pk=self.pk)
        )


class ImageShare(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name="imageshare_grantor_grantee_diff_check",
                condition=~Q(grantor=F("grantee")),
            ),
            models.UniqueConstraint(
                name="imageshare_grantor_image_grantee_unique",
                fields=["grantor", "image", "grantee"],
            ),
        ]

    grantor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="shares")
    image = models.ForeignKey(Image, on_delete=models.CASCADE)
    grantee = models.ForeignKey(User, on_delete=models.CASCADE)


class ImagePermissions:
    model = Image
    perms = ["view_image", "view_full_metadata"]
    filters = {
        "view_image": "view_image_list",
        "view_full_metadata": "view_full_metadata_list",
    }

    @staticmethod
    def view_full_metadata_list(
        user_obj: User, qs: QuerySet[Image] | None = None
    ) -> QuerySet[Image]:
        # Allows viewing unstructured metadata as well as the metadata history.
        #
        # This is only used in an SSR context, the API doesn't yet reveal more.
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_staff:
            return qs
        if not user_obj.is_anonymous:
            return qs.filter(accession__cohort__contributor__owners=user_obj)

        return qs.none()

    @staticmethod
    def view_full_metadata(user_obj: User, obj: Image) -> bool:
        return ImagePermissions.view_full_metadata_list(user_obj).contains(obj)

    @staticmethod
    def view_image_list(user_obj: User, qs: QuerySet[Image] | None = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            image_visibility_requirements = Q(public=True)

            if user_obj.owned_contributors.exists():
                image_visibility_requirements |= Q(
                    # this needs list coercion because otherwise it will be a subquery that contains
                    # the user_id, which doesn't allow users with identical privileges to share
                    # the query cache.
                    accession__cohort__contributor_id__in=list(
                        user_obj.owned_contributors.order_by().values_list("id", flat=True)
                    )
                )

            if user_obj.imageshare_set.exists():
                # this is the worst case scenario where we have to put the specific user into the
                # query, guaranteeing that they won't share the cache with others.
                # this is also the only portion that demands a left join, forcing the
                # caller to wrap the query in a distinct() call.
                image_visibility_requirements |= Q(shares=user_obj)

            # Note: permissions here must be also modified in build_elasticsearch_query and
            # LesionPermissions.view_lesion_list.
            return qs.filter(
                image_visibility_requirements,
            )
        else:
            return qs.public()

    @staticmethod
    def view_image(user_obj: User, obj: Image) -> bool:
        return ImagePermissions.view_image_list(user_obj).contains(obj)


Image.perms_class = ImagePermissions
