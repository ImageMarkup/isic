from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.urls import path
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from isic.auth import IsAuthenticated, is_application
from isic.core.pagination import paginate
from isic.core.serializers import StrictSerializer
from isic.engagement.models import EngagementProfile
from isic.ingest.api import CohortSerializer, ContributorSerializer, default_cohort_qs
from isic.ingest.models import Accession
from isic.ingest.models.accession import AccessionState

IsEngagementService = is_application("ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID")


class EngagementProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = EngagementProfile
        fields = ["created", "default_contributor", "default_cohort"]

    default_contributor = ContributorSerializer()
    default_cohort = CohortSerializer()


# this is only meant to be consumed by the engagement platform, so it's left out of the
# public schema.
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def engagement_profile(request):
    qs = EngagementProfile.objects.prefetch_related(
        "default_contributor__owners",
        # the cohort is prefetched rather than select_related so it carries the accession_count
        # annotation CohortSerializer expects.
        Prefetch("default_cohort", queryset=default_cohort_qs),
    )
    return Response(EngagementProfileSerializer(get_object_or_404(qs, user=request.user)).data)


class EngagementAccessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accession
        fields = ["id", "cohort", "external_id", "state", "isic_id", "public"]

    external_id = serializers.CharField(source="engagement.external_id")
    state = serializers.CharField()
    isic_id = serializers.SerializerMethodField()
    public = serializers.SerializerMethodField()

    def get_isic_id(self, obj: Accession) -> str | None:
        return obj.image.isic_id if obj.published else None

    def get_public(self, obj: Accession) -> bool | None:
        return obj.image.public if obj.published else None


class EngagementAccessionFilterSerializer(StrictSerializer):
    state = serializers.ChoiceField(
        choices=[state.value for state in AccessionState], allow_null=True, default=None
    )
    # capped at the maximum page size so a full length request is always a single page.
    external_ids = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        max_length=100,
        allow_null=True,
        default=None,
    )


# this is a POST because the filters belong in a body rather than a query string. it should become
# QUERY once Django REST framework supports it, which keeps the semantics of a read while still
# taking a body. until then the cursor links this returns are URLs the caller has to POST the same
# body to.
@api_view(["POST"])
@permission_classes([IsEngagementService])
def engagement_accession_list(request):
    filters = EngagementAccessionFilterSerializer(data=request.data)
    filters.is_valid(raise_exception=True)

    qs = Accession.objects.select_related(
        "image", "review", "engagement"
    ).from_engagement_platform()

    if filters.validated_data["external_ids"] is not None:
        qs = qs.filter(engagement__external_id__in=filters.validated_data["external_ids"])

    if filters.validated_data["state"] is not None:
        qs = qs.with_state(AccessionState(filters.validated_data["state"]))

    return paginate(request, qs, EngagementAccessionSerializer)


@api_view(["GET"])
@permission_classes([IsEngagementService])
def engagement_accession_detail(request, external_id: str):
    accession = get_object_or_404(
        Accession.objects.select_related(
            "image", "review", "engagement"
        ).from_engagement_platform(),
        engagement__external_id=external_id,
    )
    return Response(EngagementAccessionSerializer(accession).data)


urlpatterns = [
    path("profile/", engagement_profile, name="engagement_profile"),
    path(
        "accessions/",
        engagement_accession_list,
        name="engagement_accession_list",
    ),
    path(
        "accessions/<external_id>/",
        engagement_accession_detail,
        name="engagement_accession_detail",
    ),
]
