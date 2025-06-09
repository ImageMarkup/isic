import secrets
from typing import Any, TypedDict

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.postgres.aggregates import BoolAnd
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Case, OuterRef, Value, When
from django.db.models.aggregates import Count
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import Exists, F, Window
from django.db.models.functions import Concat
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.urls import reverse
from elasticsearch.dsl import Search
from elasticsearch.dsl.query import Q as ESQ

from isic.core.constants import LESION_ID_REGEX


def get_lesion_count_for_user(user: User | AnonymousUser) -> int:
    from isic.core.search import get_elasticsearch_client

    es = get_elasticsearch_client()

    if user.is_staff:
        return es.count(index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX)["count"]

    should = [ESQ("term", **{"images.public": True})]

    # these are structured to make the search dictionary as cacheable as possible.
    # similar to the logic in build_elasticsearch_query.
    if user.is_authenticated:
        if user.owned_contributors.exists():
            should += [
                ESQ("term", **{"images.contributor_owner_ids": user.pk}),
            ]

        if user.imageshare_set.exists():
            should += [
                ESQ("term", **{"images.shared_to": user.pk}),
            ]

    # find all documents where it's NOT true that the nested images array does NOT
    # contain any images that match should (OR of should).
    query = (
        Search(using=es, index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX)
        .query(
            "bool",
            must_not=[
                ESQ(
                    "nested",
                    path="images",
                    query=ESQ(
                        "bool",
                        must_not=[ESQ("bool", should=should)],
                    ),
                )
            ],
        )
        .extra(track_total_hits=True, size=0)
    )

    return query.execute().hits.total.value


def _default_id():
    while True:
        lesion_id = f"IL_{secrets.randbelow(9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the Lesion table
        if not Lesion.objects.filter(id=lesion_id).exists():
            return lesion_id


class LesionInfo(TypedDict):
    index_image_id: str

    images_count: int
    outcome_diagnosis: str
    outcome_diagnosis_1: str
    longitudinally_monitored: bool


class LesionQuerySet(models.QuerySet["Lesion"]):
    def has_images(self):
        from isic.ingest.models import Accession

        return self.filter(
            Exists(Accession.objects.filter(lesion_id=OuterRef("id"), image__isnull=False))
        )

    def with_total_info(self):
        return (
            self.with_index_image()
            .with_fq_diagnosis()
            .annotate(
                images_count=Window(
                    expression=Count("accessions__image"),
                    partition_by=[F("id")],
                ),
                outcome_diagnosis=F("fq_diagnosis"),
                outcome_diagnosis_1=F("accessions__diagnosis_1"),
            )
            # this is hard to do without defining a new type of expression because django
            # wants to perform group by on subqueries.
            .extra(
                select={
                    "longitudinally_monitored": "select count(distinct acquisition_day) > 1 from ingest_accession where ingest_accession.lesion_id = ingest_lesion.id"  # noqa: E501
                }
            )
        )

    def with_fq_diagnosis(self):
        return self.alias(
            fq_diagnosis=Case(
                When(accessions__diagnosis_1__isnull=True, then=Value(None)),
                default=Concat(
                    Case(
                        When(accessions__diagnosis_1__isnull=True, then=Value("")),
                        default="accessions__diagnosis_1",
                    ),
                    Case(
                        When(accessions__diagnosis_2__isnull=True, then=Value("")),
                        default=Value(":"),
                    ),
                    Case(
                        When(accessions__diagnosis_2__isnull=True, then=Value("")),
                        default="accessions__diagnosis_2",
                    ),
                    Case(
                        When(accessions__diagnosis_3__isnull=True, then=Value("")),
                        default=Value(":"),
                    ),
                    Case(
                        When(accessions__diagnosis_3__isnull=True, then=Value("")),
                        default="accessions__diagnosis_3",
                    ),
                    Case(
                        When(accessions__diagnosis_4__isnull=True, then=Value("")),
                        default=Value(":"),
                    ),
                    Case(
                        When(accessions__diagnosis_4__isnull=True, then=Value("")),
                        default="accessions__diagnosis_4",
                    ),
                    Case(
                        When(accessions__diagnosis_5__isnull=True, then=Value("")),
                        default=Value(":"),
                    ),
                    Case(
                        When(accessions__diagnosis_5__isnull=True, then=Value("")),
                        default="accessions__diagnosis_5",
                    ),
                ),
            )
        )

    def with_index_image(self):
        """
        Return a queryset with the diagnosis of the lesion annotated.

        This excludes accessions that are missing an image or have been reviewed and rejected.
        """
        return (
            self.annotate(index_image_id=F("accessions__image__isic_id"))
            .exclude(accessions__image=None)
            .exclude(accessions__review__value=False)
            .alias(
                important_image_type=Case(
                    When(accessions__image_type="dermoscopic", then=0),
                    When(accessions__image_type="clinical: close-up", then=1),
                    When(accessions__image_type="TBP tile: close-up", then=2),
                    When(accessions__image_type="clinical: overview", then=3),
                    When(accessions__image_type="TBP tile: overview", then=4),
                    default=5,
                )
            )
            .order_by(
                "id",
                "-accessions__concomitant_biopsy",
                F("accessions__acquisition_day").asc(nulls_last=True),
                "important_image_type",
                "accessions__id",
            )
            .distinct("id")
        )


class LesionManager(models.Manager["Lesion"]):
    def get_queryset(self):
        return LesionQuerySet(self.model, using=self._db)

    def with_total_info(self):
        return self.get_queryset().with_total_info()

    def with_fq_diagnosis(self):
        return self.get_queryset().with_fq_diagnosis()

    def with_index_image(self):
        return self.get_queryset().with_index_image()

    def has_images(self):
        return self.get_queryset().has_images()


class EsLesionDocument(TypedDict):
    lesion_id: str
    images: list[dict[str, Any]]


class Lesion(models.Model):
    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=12,
        validators=[RegexValidator(f"^{LESION_ID_REGEX}$")],
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="lesions")
    private_lesion_id = models.CharField(max_length=255)

    objects = LesionManager()

    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_lesion_id", "cohort"], name="unique_lesion"),
            CheckConstraint(
                name="lesion_id_valid_format",
                condition=Q(id__regex=f"^{LESION_ID_REGEX}$"),
            ),
        ]

    def __str__(self):
        return f"{self.private_lesion_id}->{self.id}"

    def get_absolute_url(self):
        return reverse("core/lesion-detail", kwargs={"identifier": self.id})

    def to_elasticsearch_document(self, *, body_only: bool = False) -> dict | EsLesionDocument:
        document: EsLesionDocument = {"lesion_id": self.pk, "images": []}

        for accession in self.accessions.all():
            document["images"].append(
                {
                    "isic_id": accession.image.isic_id,
                    "public": accession.image.public,
                    "contributor_owner_ids": accession.image.contributor_owner_ids,
                    "shared_to": accession.image.shared_to,
                }
            )

        if body_only:
            return document

        return {"_id": self.pk, "_source": document}


class LesionPermissions:
    model = Lesion
    perms = ["view_lesion"]
    filters = {
        "view_lesion": "view_lesion_list",
    }

    @staticmethod
    def view_lesion_list(user_obj: User, qs: QuerySet[Lesion] | None = None) -> QuerySet[Lesion]:
        qs = qs if qs is not None else Lesion.objects.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            lesion_visibility_requirements = Q(accessions__image__public=True) | Q(
                # this needs list coercion because otherwise it will be a subquery that contains
                # the user_id, which doesn't allow users with identical privileges to share
                # the query cache.
                cohort__contributor_id__in=list(
                    user_obj.owned_contributors.order_by().values_list("id", flat=True)
                )
            )

            # only add the user share requirement if the user has shares, since it will put
            # the user_id into the query (making query caching less effective).
            if user_obj.imageshare_set.exists():
                lesion_visibility_requirements |= Q(user_share_id=user_obj.id)

            return qs.filter(
                id__in=Lesion.objects.values("id")
                # if an image doesn't have shares it will return null which is skipped by BoolAnd.
                # this can lead to a scenario where a lesion has a private image without shares but
                # is still visible because bool_and(null, true) = true.
                # coalesce it so that bool_and always has non-null values to work with.
                .alias(user_share_id=Coalesce(F("accessions__image__shares"), -1))
                .annotate(
                    # note that these requirements are copied from ImagePermissions.view_image_list
                    visible=BoolAnd(lesion_visibility_requirements)
                )
                .filter(visible=True)
                .values("id")
            )
        else:
            return qs.filter(
                id__in=Lesion.objects.values("id")
                .annotate(visible=BoolAnd(Q(accessions__image__public=True)))
                .filter(visible=True)
                .values("id")
            )

    @staticmethod
    def view_lesion(user_obj: User, obj: Lesion) -> bool:
        return LesionPermissions.view_lesion_list(user_obj).contains(obj)


Lesion.perms_class = LesionPermissions  # type: ignore[attr-defined]
