import random

from django.contrib.auth.models import User
from django.contrib.postgres.aggregates import BoolAnd
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F
from django.db.models.functions.comparison import Coalesce
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from isic.core.constants import LESION_ID_REGEX


def _default_id():
    while True:
        lesion_id = f"IL_{random.randint(0, 9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the Lesion table
        if not Lesion.objects.filter(id=lesion_id).exists():
            return lesion_id


class Lesion(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_lesion_id", "cohort"], name="unique_lesion"),
            CheckConstraint(
                name="lesion_id_valid_format",
                check=Q(id__regex=f"^{LESION_ID_REGEX}$"),
            ),
        ]

    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=12,
        validators=[RegexValidator(f"^{LESION_ID_REGEX}$")],
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="lesions")
    private_lesion_id = models.CharField(max_length=255)

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
        elif user_obj.is_authenticated:
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


Lesion.perms_class = LesionPermissions
