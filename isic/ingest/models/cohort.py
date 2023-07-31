from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, UniqueConstraint
from django.db.models.query import QuerySet
from django.urls import reverse
from django.utils.safestring import mark_safe

# TODO: way to view failed/skipped  accessions
from isic.core.models import CopyrightLicense, CreationSortedTimeStampedModel

from .contributor import Contributor


class Cohort(CreationSortedTimeStampedModel):
    class Meta(CreationSortedTimeStampedModel.Meta):
        constraints = [
            UniqueConstraint(
                name="cohort_unique_girder_id", fields=["girder_id"], condition=~Q(girder_id="")
            )
        ]

    contributor = models.ForeignKey(Contributor, on_delete=models.PROTECT, related_name="cohorts")
    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    girder_id = models.CharField(blank=True, max_length=24, help_text="The dataset_id from Girder.")

    name = models.CharField(
        max_length=255,
        help_text=mark_safe(
            "The name of your Cohort. "
            "<strong>This is private</strong>, and will "
            "not be published along with your images."
        ),
    )
    description = models.TextField(
        help_text=mark_safe(
            "The description of your Cohort."
            "<strong>This is private</strong>, and will not be published along "
            "with your images."
        )
    )

    default_copyright_license = models.CharField(choices=CopyrightLicense.choices, max_length=255)

    # required if default_copyright_license is CC-BY-*
    attribution = models.CharField(
        help_text="The institution name that should be attributed.", max_length=200
    )

    collection = models.OneToOneField(
        "core.Collection", null=True, on_delete=models.SET_NULL, related_name="cohort"
    )

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        return reverse("cohort-detail", args=[self.id])


class CohortPermissions:
    model = Cohort
    perms = ["view_cohort", "add_accession", "edit_cohort"]
    filters = {"view_cohort": "view_cohort_list", "edit_cohort": "edit_cohort_list"}

    @staticmethod
    def view_cohort_list(user_obj: User, qs: QuerySet[Cohort] | None = None) -> QuerySet[Cohort]:
        qs = qs if qs is not None else Cohort._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(contributor__owners__in=[user_obj])
        else:
            return qs.none()

    @staticmethod
    def edit_cohort_list(user_obj: User, qs: QuerySet[Cohort] | None = None) -> QuerySet[Cohort]:
        qs = qs if qs is not None else Cohort._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(contributor__owners__in=[user_obj])
        else:
            return qs.none()

    @staticmethod
    def view_cohort(user_obj, obj):
        return CohortPermissions.view_cohort_list(user_obj).contains(obj)

    @staticmethod
    def edit_cohort(user_obj, obj):
        return CohortPermissions.edit_cohort_list(user_obj).contains(obj)

    @staticmethod
    def add_accession(user_obj: User, obj: Cohort) -> bool:
        if obj:
            return user_obj.is_authenticated and obj.contributor.owners.contains(user_obj)


Cohort.perms_class = CohortPermissions
