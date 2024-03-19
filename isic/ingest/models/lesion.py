import secrets

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import BoolAnd
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import OuterRef
from django.db.models.aggregates import Count
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import Case, Exists, F, When, Window
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from isic.core.constants import LESION_ID_REGEX


def _default_id():
    while True:
        lesion_id = f"IL_{secrets.randbelow(9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the Lesion table
        if not Lesion.objects.filter(id=lesion_id).exists():
            return lesion_id


class LesionQuerySet(models.QuerySet):
    def has_images(self):
        from isic.ingest.models import Accession

        return self.filter(
            Exists(Accession.objects.filter(lesion_id=OuterRef("id"), image__isnull=False))
        )

    def with_total_info(self):
        return (
            self.with_index_image()
            .annotate(
                images_count=Window(
                    expression=Count("accessions__image"),
                    partition_by=[F("id")],
                ),
                outcome_diagnosis=F("accessions__diagnosis"),
                outcome_benign_malignant=F("accessions__benign_malignant"),
            )
            # this is hard to do without defining a new type of expression because django
            # wants to perform group by on subqueries.
            .extra(
                select={
                    "longitudinally_monitored": "select count(distinct acquisition_day) > 1 from ingest_accession where ingest_accession.lesion_id = ingest_lesion.id"  # noqa: E501
                }
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


class Lesion(models.Model):
    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=12,
        validators=[RegexValidator(f"^{LESION_ID_REGEX}$")],
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="lesions")
    private_lesion_id = models.CharField(max_length=255)

    objects = LesionQuerySet.as_manager()

    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_lesion_id", "cohort"], name="unique_lesion"),
            CheckConstraint(
                name="lesion_id_valid_format",
                check=Q(id__regex=f"^{LESION_ID_REGEX}$"),
            ),
        ]

    def __str__(self):
        return f"{self.private_lesion_id}->{self.id}"


class LesionPermissions:
    model = Lesion
    perms = ["view_lesion"]
    filters = {"view_lesion": "view_lesion_list"}

    @staticmethod
    def view_lesion_list(user_obj: User, qs: QuerySet[Lesion] | None = None) -> QuerySet[Lesion]:
        qs = qs if qs is not None else Lesion.objects.all()

        if user_obj.is_staff:
            return qs
        if user_obj.is_authenticated:
            return qs.filter(
                id__in=Lesion.objects.values("id")
                # if an image doesn't have shares it will return null which is skipped by BoolAnd.
                # this can lead to a scenario where a lesion has a private image without shares but
                # is still visible because bool_and(null, true) = true.
                # coalesce it so that bool_and always has non-null values to work with.
                .alias(user_share_id=Coalesce(F("accessions__image__shares"), -1))
                .annotate(
                    # note that these requirements are copied from ImagePermissions.view_image_list
                    visible=BoolAnd(
                        Q(accessions__image__public=True)
                        | Q(cohort__contributor__owners=user_obj)
                        | Q(user_share_id=user_obj.id)
                    )
                )
                .filter(visible=True)
                .values("id")
            )

        return qs.filter(
            id__in=Lesion.objects.values("id")
            .annotate(visible=BoolAnd(Q(accessions__image__public=True)))
            .filter(visible=True)
            .values("id")
        )

    @staticmethod
    def view_lesion(user_obj: User, obj: Lesion) -> bool:
        return LesionPermissions.view_lesion_list(user_obj).contains(obj)


Lesion.perms_class = LesionPermissions
