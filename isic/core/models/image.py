from copy import deepcopy

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

from isic.core.dsl import django_parser, parse_query
from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Accession

from .isic_id import IsicId


class ImageQuerySet(models.QuerySet):
    def from_search_query(self, query: str):
        if query == "":
            return self
        else:
            return self.filter(parse_query(django_parser, query) or Q())

    def with_elasticsearch_properties(self):
        return self.select_related("accession__cohort").annotate(
            coll_pks=ArrayAgg("collections", distinct=True, default=[]),
            contributor_owner_ids=ArrayAgg(
                "accession__cohort__contributor__owners", distinct=True, default=[]
            ),
            shared_to=ArrayAgg("shares", distinct=True, default=[]),
        )

    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)


class Image(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        indexes = [
            # icontains uses Upper(name) for searching
            GinIndex(OpClass(Upper("isic"), name="gin_trgm_ops"), name="isic_name_gin")
        ]

    accession = models.OneToOneField(
        Accession,
        on_delete=models.PROTECT,
    )
    # This should typically be referenced as ".isic_id"
    isic = models.OneToOneField(
        IsicId,
        on_delete=models.PROTECT,
        default=IsicId.safe_create,
        editable=False,
        verbose_name="isic id",
    )
    # The creator is the person who published the accessions.
    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="published_images")

    # index is used because public is filtered in every permissions check
    public = models.BooleanField(default=False, db_index=True)

    shares = models.ManyToManyField(
        User, through="ImageShare", through_fields=["image", "recipient"]
    )

    objects = ImageQuerySet.as_manager()

    def __str__(self):
        return self.isic_id

    def get_absolute_url(self):
        return reverse("core/image-detail", args=[self.pk])

    @property
    def has_patient(self) -> bool:
        return self.accession.patient_id is not None

    @property
    def has_lesion(self) -> bool:
        return self.accession.lesion_id is not None

    @property
    def metadata(self) -> dict:
        """
        Return the metadata for an image.

        Note that the metadata for the image is sanitized unlike the metadata for the accession
        which is behind the "firewall" of ingest. This includes rounded ages and obfuscated
        longitudinal IDs.
        """
        image_metadata = deepcopy(self.accession.metadata)

        if "age" in image_metadata:
            image_metadata["age_approx"] = Accession._age_approx(image_metadata["age"])
            del image_metadata["age"]

        if self.has_lesion:
            image_metadata["lesion_id"] = self.accession.lesion_id

        if self.has_patient:
            image_metadata["patient_id"] = self.accession.patient_id

        return image_metadata

    def to_elasticsearch_document(self, body_only=False) -> dict:
        # Can only be called on images that were fetched with with_elasticsearch_properties.
        document = {
            "id": self.pk,
            "created": self.created,
            "isic_id": self.isic_id,
            "public": self.public,
            "copyright_license": self.accession.copyright_license,
            # TODO: make sure these fields can't be searched on
            "contributor_owner_ids": self.contributor_owner_ids,
            "shared_to": self.shared_to,
            "collections": self.coll_pks,
        }

        document.update(self.metadata)

        if body_only:
            return document
        else:
            # index the document by image.pk so it can be updated later.
            return {"_id": self.pk, "_source": document}

    def same_patient_images(self) -> QuerySet["Image"]:
        if not self.has_patient:
            return Image.objects.none()

        return (
            Image.objects.filter(accession__cohort_id=self.accession.cohort_id)
            .filter(**{"accession__patient_id": self.accession.patient_id})
            .exclude(pk=self.pk)
        )

    def same_lesion_images(self) -> QuerySet["Image"]:
        if not self.has_lesion:
            return Image.objects.none()

        return (
            Image.objects.filter(accession__cohort_id=self.accession.cohort_id)
            .filter(**{"accession__lesion_id": self.accession.lesion_id})
            .exclude(pk=self.pk)
        )


class ImageShare(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name="imageshare_creator_recipient_diff_check", check=~Q(creator=F("recipient"))
            )
        ]

    creator = models.ForeignKey(User, on_delete=models.PROTECT, related_name="shares")
    image = models.ForeignKey(Image, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE)


class ImagePermissions:
    model = Image
    perms = ["view_image", "view_full_metadata"]
    filters = {"view_image": "view_image_list", "view_full_metadata": "view_full_metadata_list"}

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
        elif not user_obj.is_anonymous:
            return qs.filter(accession__cohort__contributor__owners=user_obj)
        else:
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
            # Note: permissions here must be also modified in build_elasticsearch_query
            return qs.filter(
                Q(public=True)
                | Q(accession__cohort__contributor__owners=user_obj)
                | Q(shares=user_obj)
            )
        else:
            return qs.public()

    @staticmethod
    def view_image(user_obj: User, obj: Image) -> bool:
        return ImagePermissions.view_image_list(user_obj).contains(obj)


Image.perms_class = ImagePermissions
