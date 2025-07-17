from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.functions import Upper
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .image import Image


class CollectionQuerySet(models.QuerySet):
    def pinned(self):
        return self.filter(pinned=True)

    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)

    def magic(self):
        return self.exclude(cohort=None)

    def regular(self):
        # regular means not magic
        return self.filter(cohort=None)


class Collection(TimeStampedModel):
    """
    Collections are unordered groups of images.

    Collections are locked and then nothing can be modified except for
    adding a DOI. Once locked, no images can be added either.

    A collection can be public or private. Public collections cannot contain
    private images.
    """

    class Meta(TimeStampedModel.Meta):
        unique_together = [["creator", "name"]]
        constraints = [
            UniqueConstraint(
                name="collection_pinned_has_unique_name",
                fields=["name"],
                condition=Q(pinned=True),
            ),
            CheckConstraint(
                name="collection_pinned_implies_public",
                condition=Q(pinned=False) | Q(public=True),
            ),
        ]
        indexes = [
            # icontains uses Upper(name) for searching
            GinIndex(OpClass(Upper("name"), name="gin_trgm_ops"), name="collection_name_gin")
        ]

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    images = models.ManyToManyField(Image, related_name="collections", through="CollectionImage")

    # unique per user. names of pinned collections can't be used.
    name = models.CharField(max_length=200)
    description = models.TextField(
        blank=True,
        help_text='Supports <a href="https://www.markdownguide.org/cheat-sheet/">markdown</a>.',
    )

    public = models.BooleanField(default=False)

    shares = models.ManyToManyField(
        User,
        through="CollectionShare",
        through_fields=("collection", "grantee"),
        related_name="collection_shares",
    )

    pinned = models.BooleanField(default=False)

    locked = models.BooleanField(default=False)

    objects = CollectionQuerySet.as_manager()

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("core/collection-detail", args=[self.pk])

    @property
    def is_magic(self) -> bool:
        """Magic collections are collections pointed to by a cohort."""
        return hasattr(self, "cohort")

    @property
    def num_lesions(self):
        return (
            self.images.exclude(accession__lesion_id=None)
            .values("accession__lesion_id")
            .distinct()
            .count()
        )

    @property
    def num_patients(self):
        return (
            self.images.exclude(accession__patient_id=None)
            .values("accession__patient_id")
            .distinct()
            .count()
        )

    @property
    def shared_with(self):
        return [
            share.grantee
            for share in CollectionShare.objects.filter(collection=self)
            .select_related("grantee")
            .order_by("created")
            .all()
        ]

    @property
    def counts(self):
        if not hasattr(self, "cached_counts"):
            return {
                "image_count": "-",
                "lesion_count": "-",
                "patient_count": "-",
            }
        return self.cached_counts

    def full_clean(self, exclude=None, validate_unique=True):  # noqa: FBT002
        if self.pk and self.public and self.images.private().exists():  # type: ignore[attr-defined]
            raise ValidationError("Can't make collection public, it contains private images.")

        return super().full_clean(exclude=exclude, validate_unique=validate_unique)


class CollectionImage(models.Model):
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                name="collectionimage_collection_image_unique",
                fields=["collection", "image"],
            ),
        ]

    def __str__(self):
        return f"collection: {self.collection_id} - image: {self.image_id}"


class CollectionShare(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name="collectionshare_grantor_grantee_diff_check",
                condition=~Q(grantor=F("grantee")),
            ),
            UniqueConstraint(
                name="collectionshare_grantor_collection_grantee_unique",
                fields=["grantor", "collection", "grantee"],
            ),
        ]

    grantor = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="collection_shares_given"
    )
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    grantee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="collection_shares_received"
    )


class CollectionPermissions:
    model = Collection
    perms = [
        "view_collection",
        "edit_collection",
        "create_doi",
        "add_images",
        "remove_images",
    ]
    filters = {
        "view_collection": "view_collection_list",
        "create_doi": "create_doi_list",
    }

    @staticmethod
    def _is_creator_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            return qs.filter(creator=user_obj)

        return qs.none()

    @staticmethod
    def view_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            return qs.filter(Q(public=True) | Q(creator=user_obj) | Q(shares=user_obj))

        return qs.public()

    @staticmethod
    def view_collection(user_obj, obj):
        return CollectionPermissions.view_collection_list(user_obj).contains(obj)

    @staticmethod
    def create_doi_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs

        return qs.none()

    @staticmethod
    def create_doi(user_obj: User, obj: Collection) -> bool:
        return CollectionPermissions.create_doi_list(user_obj).contains(obj)

    @staticmethod
    def add_images_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        return CollectionPermissions._is_creator_list(user_obj, qs)

    @staticmethod
    def add_images(user_obj, obj: Collection):
        return CollectionPermissions.add_images_list(user_obj).contains(obj)

    # just alias add_images for now.
    @staticmethod
    def remove_images(user_obj, obj: Collection):
        return CollectionPermissions.add_images(user_obj, obj)

    @staticmethod
    def edit_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        return CollectionPermissions._is_creator_list(user_obj, qs)

    @staticmethod
    def edit_collection(user_obj, obj: Collection):
        return CollectionPermissions.add_images_list(user_obj).contains(obj)


Collection.perms_class = CollectionPermissions
