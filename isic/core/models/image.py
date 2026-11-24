from __future__ import annotations

from copy import deepcopy
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.expressions import Exists, F, OuterRef
from django.db.models.functions import Upper
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from pgvector.django import CosineDistance

from isic.core.dsl import django_parser, parse_query
from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId

if TYPE_CHECKING:
    from django.db.models.query import QuerySet


class ImageQuerySet(models.QuerySet["Image"]):
    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)

    def from_search_query(self, query: str):
        if query == "":
            return self
        return self.filter(parse_query(django_parser, query) or Q())


_BaseImageManager = models.Manager.from_queryset(ImageQuerySet)


class ImageManager(_BaseImageManager):
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

    def has_embedding(self):
        return self.filter(embedding_relation__isnull=False)


class Image(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        ordering = ["created"]

        constraints = [
            CheckConstraint(
                name="image_pinned_implies_public",
                condition=Q(pinned=0) | Q(public=True),
            ),
        ]

        indexes = [
            # icontains uses Upper(name) for searching
            GinIndex(OpClass(Upper("isic"), name="gin_trgm_ops"), name="isic_name_gin"),
            # Used when sorting images by pinned state and then by created timestamp
            models.Index(fields=["-pinned", "created"], name="pinned_created_index"),
            # Used when listing a user's newest images on the user detail page
            models.Index(fields=["creator", "created"], name="image_creator_created_index"),
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

    pinned = models.PositiveSmallIntegerField(default=0)

    shares: models.ManyToManyField[User, ImageShare] = models.ManyToManyField(
        User, through="ImageShare", through_fields=("image", "grantee")
    )

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
        return hasattr(self, "embedding_relation")

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

    def to_elasticsearch_document(self, *, source_only=False) -> dict:
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

        if source_only:
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

    def similar_images(self) -> QuerySet[Image]:
        if not self.has_embedding:
            return Image.objects.none()

        return (
            Image.objects.filter(embedding_relation__isnull=False)
            .exclude(pk=self.pk)
            .annotate(
                distance=CosineDistance(
                    "embedding_relation__embedding", self.embedding_relation.embedding
                )
            )
            .order_by("distance")
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
    image = models.ForeignKey(Image, on_delete=models.CASCADE, related_name="image_shares")
    grantee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="image_shares_received"
    )


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
    def visible_image_q(user_obj: User) -> Q:
        """
        Return the images a non-staff user can see, as a predicate on an Image queryset.

        Each branch is a column test, a join that can't multiply rows or a correlated subquery, so
        filtering by it never needs distinct(). build_elasticsearch_query mirrors it.
        """
        if not user_obj.is_authenticated:
            return Q(public=True)

        image_visibility_requirements = Q(public=True)

        # the contributor ids are inlined so the query carries no user id and users with the same
        # privileges share the query cache. the list doubles as the check for whether the branch
        # is needed, so there is no separate exists() query here. this stays a join: the accession
        # is one-to-one and its cohort many-to-one, so it can't multiply rows, and as a subquery
        # postgres would hash every accession the user owns before returning the first row.
        owned_contributor_ids = list(
            user_obj.owned_contributors.order_by().values_list("id", flat=True)
        )
        if owned_contributor_ids:
            image_visibility_requirements |= Q(
                accession__cohort__contributor_id__in=owned_contributor_ids
            )

        # the only branch that puts the user id into the query, so it's only added for users with
        # shares; everyone else keeps sharing the cache. nothing from the shares is inlined, so an
        # exists() is the cheapest way to find out.
        if user_obj.image_shares_received.exists():
            image_visibility_requirements |= Exists(
                ImageShare.objects.filter(image_id=OuterRef("pk"), grantee=user_obj)
            )

        return image_visibility_requirements

    @staticmethod
    def view_image_list(user_obj: User, qs: QuerySet[Image] | None = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()

        if user_obj.is_staff:
            return qs

        return qs.filter(ImagePermissions.visible_image_q(user_obj))

    @staticmethod
    def view_image(user_obj: User, obj: Image) -> bool:
        return ImagePermissions.view_image_list(user_obj).contains(obj)


Image.perms_class = ImagePermissions
