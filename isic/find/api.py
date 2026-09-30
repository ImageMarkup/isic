from functools import partial

from django.contrib.auth.models import User
from django.db.models.aggregates import Count
from django.urls import path
from jaro import jaro_winkler_metric
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from isic.auth import IsAuthenticated, IsStaff
from isic.core.api.collection import CollectionSerializer
from isic.core.models import Collection
from isic.core.permissions import get_visible_objects
from isic.find.find import quickfind_execute
from isic.ingest.api import CohortSerializer, ContributorAutocompleteSerializer
from isic.ingest.models import Cohort, Contributor

AUTOCOMPLETE_LIMIT = 20


class QuerySerializer(serializers.Serializer):
    query = serializers.CharField(allow_blank=True, trim_whitespace=False)

    def validate_query(self, v: str) -> str:
        if len(v) < 3:
            raise serializers.ValidationError("Query too short.")

        if v.lower() in "isic_":
            # Every image starts with ISIC_, so this would produce
            # far too many results to be meaningful. Force the user
            # to enter more information.
            raise serializers.ValidationError("Query too common.")

        return v


@api_view(["GET"])
@permission_classes([AllowAny])
def quickfind(request):
    params = QuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    return Response(quickfind_execute(params.validated_data["query"], request.user))


class AutocompleteQuerySerializer(serializers.Serializer):
    query = serializers.CharField(min_length=3, trim_whitespace=False)


def autocomplete_query(request) -> str:
    params = AutocompleteQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    return params.validated_data["query"]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cohort_autocomplete(request):
    query = autocomplete_query(request)
    qs = get_visible_objects(
        request.user,
        "ingest.view_cohort",
        Cohort.objects.filter(name__icontains=query).annotate(accession_count=Count("accessions")),
    )
    return Response(CohortSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def contributor_autocomplete(request):
    query = autocomplete_query(request)
    qs = get_visible_objects(
        request.user,
        "ingest.view_contributor",
        Contributor.objects.filter(institution_name__icontains=query).order_by("institution_name"),
    )[:AUTOCOMPLETE_LIMIT]
    return Response(ContributorAutocompleteSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def find_collection_autocomplete(request):
    query = autocomplete_query(request)
    # exclude magic collections
    qs = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.filter(name__icontains=query, cohort=None).order_by("name", "-created"),
    )
    distance = partial(jaro_winkler_metric, query.upper())
    collections = sorted(
        qs, key=lambda collection: distance(collection.name.upper()), reverse=True
    )[:10]
    return Response(CollectionSerializer(collections, many=True).data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


@api_view(["GET"])
@permission_classes([IsStaff])
def user_autocomplete(request):
    query = autocomplete_query(request)
    qs = User.objects.filter(is_active=True, email__icontains=query).order_by("email")
    distance = partial(jaro_winkler_metric, query.upper())
    users = sorted(qs, key=lambda user: distance(user.email.upper()), reverse=True)[:10]
    return Response(UserSerializer(users, many=True).data)


quickfind_urlpatterns = [
    path("", quickfind, name="quickfind"),
]

autocomplete_urlpatterns = [
    path("cohort/", cohort_autocomplete, name="cohort_autocomplete"),
    path("contributor/", contributor_autocomplete, name="contributor_autocomplete"),
    path(
        "collection/",
        find_collection_autocomplete,
        name="find_collection_autocomplete",
    ),
    path("user/", user_autocomplete, name="user_autocomplete"),
]
