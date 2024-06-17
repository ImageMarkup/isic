from functools import partial

from django.contrib.auth.models import User
from django.db.models.aggregates import Count
from django.http.request import HttpRequest
from django.http.response import JsonResponse
from jaro import jaro_winkler_metric
from ninja import ModelSchema, Query, Router, Schema
from pydantic import field_validator

from isic.core.api.collection import CollectionOut
from isic.core.models import Collection
from isic.core.permissions import get_visible_objects
from isic.find.find import quickfind_execute
from isic.ingest.api import CohortOut
from isic.ingest.models import Cohort

router = Router()
autocomplete_router = Router()


class QueryIn(Schema):
    query: str

    model_config = {"extra": "forbid"}

    @field_validator("query")
    @classmethod
    def query_min_length(cls, v: str):
        if len(v) < 3:
            raise ValueError("Query too short.")
        return v

    @field_validator("query")
    @classmethod
    def query_too_common(cls, v: str):
        if v.lower() in "isic_":
            # Every image starts with ISIC_, so this would produce
            # far too many results to be meaningful. Force the user
            # to enter more information.
            raise ValueError("Query too common.")
        return v


@router.get("/", include_in_schema=False)
def quickfind(request, payload: QueryIn = Query(...)):
    return JsonResponse(quickfind_execute(payload.query, request.user), safe=False)


@autocomplete_router.get("/cohort/", response=list[CohortOut], include_in_schema=False)
def cohort_autocomplete(request: HttpRequest, query=Query(..., min_length=3)):
    return get_visible_objects(
        request.user,
        "ingest.view_cohort",
        Cohort.objects.filter(name__icontains=query).annotate(accession_count=Count("accessions")),
    )


@autocomplete_router.get("/collection/", response=list[CollectionOut], include_in_schema=False)
def collection_autocomplete(request: HttpRequest, query=Query(..., min_length=3)):
    # exclude magic collections
    qs = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.filter(name__icontains=query, cohort=None).order_by("name", "-created"),
    )
    distance = partial(jaro_winkler_metric, query.upper())
    return sorted(qs, key=lambda collection: distance(collection.name.upper()), reverse=True)[:10]


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


@autocomplete_router.get("/user/", response=list[UserOut], include_in_schema=False)
def user_autocomplete(request: HttpRequest, query=Query(..., min_length=3)):
    if not request.user.is_staff:
        return 403, {"error": "Only staff users may search for users."}

    qs = User.objects.filter(is_active=True, email__icontains=query).order_by("email")
    distance = partial(jaro_winkler_metric, query.upper())
    return sorted(qs, key=lambda user: distance(user.email.upper()), reverse=True)[:10]
