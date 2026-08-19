from django.db.models import Prefetch
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Field, ModelSchema, Router, Schema
from ninja.pagination import paginate

from isic.auth import is_application, is_authenticated
from isic.core.pagination import CursorPagination
from isic.engagement.models import EngagementProfile
from isic.ingest.api import CohortOut, ContributorOut, default_cohort_qs
from isic.ingest.models import Accession
from isic.ingest.models.accession import AccessionState
from isic.types import AuthenticatedHttpRequest

router = Router()

is_engagement_service = is_application("ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID")


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


class EngagementAccessionOut(ModelSchema):
    class Meta:
        model = Accession
        fields = ["id", "cohort"]

    external_id: str
    state: AccessionState
    isic_id: str | None
    public: bool | None

    @staticmethod
    def resolve_external_id(obj: Accession) -> str:
        return obj.engagement.external_id

    @staticmethod
    def resolve_isic_id(obj: Accession) -> str | None:
        return obj.image.isic_id if obj.published else None

    @staticmethod
    def resolve_public(obj: Accession) -> bool | None:
        return obj.image.public if obj.published else None


class EngagementAccessionFilter(Schema):
    state: AccessionState | None = None
    # capped at the maximum page size so a full length request is always a single page.
    external_ids: list[str] | None = Field(None, max_length=100)

    model_config = {"extra": "forbid"}


# this is a POST because the filters belong in a body rather than a query string. it should become
# QUERY once django-ninja can route it, which keeps the semantics of a read while still taking a
# body. until then the cursor links this returns are URLs the caller has to POST the same body to.
@router.post(
    "/accessions/",
    response=list[EngagementAccessionOut],
    summary="Return a list of accessions that came from the engagement platform.",
    include_in_schema=False,
    auth=is_engagement_service,
)
@paginate(CursorPagination)
def engagement_accession_list(request: HttpRequest, filters: EngagementAccessionFilter):
    qs = Accession.objects.select_related(
        "image", "review", "engagement"
    ).from_engagement_platform()

    if filters.external_ids is not None:
        qs = qs.filter(engagement__external_id__in=filters.external_ids)

    if filters.state is not None:
        qs = qs.with_state(filters.state)

    return qs


@router.get(
    "/accessions/{external_id}/",
    response=EngagementAccessionOut,
    summary="Retrieve a single engagement platform accession by its engagement platform id.",
    include_in_schema=False,
    auth=is_engagement_service,
)
def engagement_accession_detail(request: HttpRequest, external_id: str):
    return get_object_or_404(
        Accession.objects.select_related(
            "image", "review", "engagement"
        ).from_engagement_platform(),
        engagement__external_id=external_id,
    )
