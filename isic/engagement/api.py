from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router

from isic.auth import is_authenticated
from isic.engagement.models import EngagementProfile
from isic.types import AuthenticatedHttpRequest

router = Router()


class EngagementProfileOut(ModelSchema):
    class Meta:
        model = EngagementProfile
        fields = [
            "created",
            "default_contributor",
            "default_cohort",
        ]


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
    return get_object_or_404(EngagementProfile, user=request.user)
