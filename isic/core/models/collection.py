from django.contrib.auth.models import User
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.functions import Upper
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel

from .doi import Doi
from .image import Image


class CollectionQuerySet(models.QuerySet):
    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)

    def magic(self):
        return self.exclude(cohort=None)

    def regular(self):
        # regular means not magic
        return self.filter(cohort=None)

    def text_search(self, value: str, rank_threshold: float = 0.0):
        vector = SearchVector("name", weight="A") + SearchVector("description", weight="B")
        return (
            self.annotate(search_rank=SearchRank(vector, SearchQuery(value)))
            .order_by("-search_rank")
            .filter(search_rank__gt=rank_threshold)
        )


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
            )
        ]
        indexes = [
            # icontains uses Upper(name) for searching
            GinIndex(OpClass(Upper("name"), name="gin_trgm_ops"), name="collection_name_gin"),
        ]

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    images = models.ManyToManyField(Image, related_name="collections")

    # unique per user. names of pinned collections can't be used.
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    public = models.BooleanField(default=False)

    shares = models.ManyToManyField(
        User,
        through="CollectionShare",
        through_fields=["collection", "recipient"],
        related_name="collection_shares",
    )

    pinned = models.BooleanField(default=False)

    doi = models.OneToOneField(Doi, on_delete=models.PROTECT, null=True, blank=True)

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
    def has_doi(self) -> bool:
        return self.doi is not None

    @property
    def doi_url(self):
        if self.doi:
            return f"https://doi.org/{self.doi}"

    def full_clean(self, exclude=None, validate_unique=True):
        if self.pk and self.public and self.images.private().exists():
            raise ValidationError("Can't make collection public, it contains private images.")

        return super().full_clean(exclude=exclude, validate_unique=validate_unique)


class CollectionShare(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        constraints = [
            CheckConstraint(
                name="collectionshare_creator_recipient_diff_check",
                check=~Q(creator=F("recipient")),
            )
        ]

    creator = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="collection_shares_given"
    )
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE)
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="collection_shares_received"
    )


class CollectionPermissions:
    model = Collection
    perms = ["view_collection", "edit_collection", "create_doi", "add_images", "remove_images"]
    filters = {"view_collection": "view_collection_list", "create_doi": "create_doi_list"}

    @staticmethod
    def _is_creator_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(creator=user_obj)
        else:
            return qs.none()

    @staticmethod
    def view_collection_list(
        user_obj: User, qs: QuerySet[Collection] | None = None
    ) -> QuerySet[Collection]:
        qs = qs if qs is not None else Collection._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(Q(public=True) | Q(creator=user_obj) | Q(shares=user_obj))
        else:
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
        else:
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
