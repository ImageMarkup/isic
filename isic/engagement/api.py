from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from isic.auth import is_authenticated
from isic.engagement.models import EngagementProfile
from isic.ingest.api import CohortOut, ContributorOut, default_cohort_qs
from isic.types import AuthenticatedHttpRequest

router = Router()


class EngagementProfileOut(ModelSchema):
    class Meta:
        model = EngagementProfile
        fields = ["created"]

    default_contributor: ContributorOut | None
    default_cohort: CohortOut | None


@router.get(
    "/profile/",
    response=EngagementProfileOut,
    summary="Retrieve the engagement profile of the currently logged in user.",
    # this is only meant to be consumed by the engagement platform, so it's left out of the
    # public schema.
    include_in_schema=False,
    auth=is_authenticated,
)
def engagement_profile(request: AuthenticatedHttpRequest):
    qs = EngagementProfile.objects.prefetch_related(
        "default_contributor__owners",
        # the cohort is prefetched rather than select_related so it carries the accession_count
        # annotation CohortOut expects.
        Prefetch("default_cohort", queryset=default_cohort_qs),
    )
    return get_object_or_404(qs, user=request.user)
