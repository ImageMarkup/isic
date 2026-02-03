from typing import Literal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from jaro import jaro_winkler_metric
from ninja import Field, ModelSchema, Query, Router, Schema
from ninja.pagination import paginate
from pydantic import field_validator
from pydantic.types import conlist, constr

from isic.core.constants import ISIC_ID_REGEX
from isic.core.models.collection import Collection
from isic.core.pagination import CursorPagination
from isic.core.permissions import get_visible_objects
from isic.core.serializers import SearchQueryIn
from isic.core.services.collection import collection_delete
from isic.core.services.collection.image import (
    collection_add_images_from_isic_ids,
    collection_remove_images_from_isic_ids,
)
from isic.core.tasks import (
    populate_collection_from_search_task,
    share_collection_with_users_task,
)
from isic.ingest.models.accession import Accession

router = Router()


# See also isic.find.api.QueryIn
class AutocompleteQueryIn(Schema):
    query: str

    model_config = {"extra": "forbid"}

    @field_validator("query")
    @classmethod
    def query_min_length(cls, v: str):
        if len(v) < 3:
            raise ValueError("Query too short.")
        return v


class CollectionOut(ModelSchema):
    class Meta:
        model = Collection
        fields = ["id", "name", "description", "public", "pinned", "locked"]

    doi: str | None = Field(None, alias="doi.id")
    doi_url: str | None = Field(None, alias="doi.external_url")


@router.get(
    "/",
    response=list[CollectionOut],
    summary="Return a list of collections.",
    include_in_schema=True,
)
@paginate(CursorPagination)
def collection_list(
    request, pinned: bool | None = None, sort: Literal["name", "created"] | None = None
) -> list[CollectionOut]:
    queryset = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())

    if pinned is not None:
        queryset = queryset.filter(pinned=pinned)

    if sort is not None:
        queryset = queryset.order_by(sort)

    return queryset


# Note that this route needs to be defined before collection_detail to resolve the ambiguity
# between the two. See https://github.com/vitalik/django-ninja/issues/507#issuecomment-1186450789.
@router.get(
    "/autocomplete/",
    response=list[CollectionOut],
    summary="Find relevant collections by auto completing by name.",
    include_in_schema=False,
)
def collection_autocomplete(
    request, payload: AutocompleteQueryIn = Query(...)
) -> list[CollectionOut]:
    qs = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.select_related("doi").filter(
            name__icontains=payload.query, locked=False
        ),
    )

    if not request.user.is_staff and request.user.is_authenticated:
        qs = qs.filter(creator=request.user)

    # sort by jaro winkler, then name to make something like "challenge" return the
    # challenge collections in order.
    collections = sorted(
        qs,
        key=lambda collection: (
            -jaro_winkler_metric(collection.name.upper(), payload.query.upper()),
            collection.name,
        ),
    )

    return collections[:20]


@router.get(
    "/{id}/",
    response=CollectionOut,
    summary="Retrieve a single collection by ID.",
    include_in_schema=True,
)
def collection_detail(request, id: int) -> CollectionOut:
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    return get_object_or_404(qs.distinct(), id=id)


@router.delete(
    "/{id}/",
    response={204: None, 400: dict, 403: dict},
    include_in_schema=False,
)
def collection_delete_(request, id: int):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.edit_collection", collection):
        return 403, {"error": "You do not have permission to delete this collection."}

    try:
        collection_delete(collection=collection)
    except ValidationError as e:
        return 400, {"error": e.message}

    return 204, None


class CollectionShareIn(Schema):
    user_ids: list[int]
    notify: bool = True


@router.post("/{id}/share/", response={202: None, 404: dict, 403: dict}, include_in_schema=False)
def collection_share_to_users(request, id: int, payload: CollectionShareIn):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.is_staff:
        return 403, {"error": "You do not have permission to share this collection."}

    share_collection_with_users_task.delay_on_commit(
        collection.id, request.user.id, payload.user_ids, notify=payload.notify
    )

    messages.add_message(
        request, messages.INFO, "Sharing collection with user(s), this may take a few minutes."
    )

    return 202, {}


@router.get(
    "/{id}/attribution/",
    summary="Retrieve attribution information of the specified collection.",
    include_in_schema=False,
)
def collection_attribution_information(request, id: int) -> list[dict[str, int]]:
    qs = get_visible_objects(request.user, "core.view_collection")
    collection = get_object_or_404(qs.distinct(), id=id)
    images = get_visible_objects(request.user, "core.view_image", collection.images.distinct())
    counts = (
        Accession.objects.filter(image__in=images)
        .values("copyright_license", "attribution")
        .annotate(count=Count("id"))
        .order_by("-count")
        .values_list("copyright_license", "attribution", "count")
    )

    return [{"license": x[0], "attribution": x[1], "count": x[2]} for x in counts]


@router.post(
    "/{id}/populate-from-search/",
    response={202: None, 403: dict, 409: dict},
    include_in_schema=False,
)
def collection_populate_from_search(request, id: int, payload: SearchQueryIn):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.add_images", collection):
        return 403, {"error": "You do not have permission to add images to this collection."}

    if collection.locked:
        return 409, {"error": "Collection is locked"}

    if collection.public and payload.to_queryset(request.user).private().exists():  # type: ignore[attr-defined]
        return 409, {"error": "Collection is public and cannot contain private images."}

    # Pass data instead of validated_data because the celery task is going to revalidate.
    # This avoids re encoding collections as a comma delimited string.
    populate_collection_from_search_task.delay_on_commit(id, request.user.pk, payload.dict())

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request, messages.INFO, "Adding images to collection, this may take a few minutes."
    )
    return 202, {}


class IsicIdList(Schema):
    isic_ids: conlist(constr(pattern=ISIC_ID_REGEX), max_length=500)  # type: ignore[valid-type]

    model_config = {"extra": "forbid"}


# TODO: refactor *-from-list methods
@router.post(
    "/{id}/populate-from-list/", response={200: None, 403: dict, 409: dict}, include_in_schema=False
)
def collection_populate_from_list(request, id, payload: IsicIdList):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.add_images", collection):
        return 403, {"error": "You do not have permission to add images to this collection."}

    if collection.locked:
        return 409, {"error": "Collection is locked"}

    summary = collection_add_images_from_isic_ids(
        user=request.user,
        collection=collection,
        isic_ids=payload.isic_ids,
    )

    return JsonResponse(summary)


@router.post(
    "/{id}/remove-from-list/", response={200: None, 403: dict, 409: dict}, include_in_schema=False
)
def remove_from_list(request, id, payload: IsicIdList):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.remove_images", collection):
        return 403, {"error": "You do not have permission to add images to this collection."}

    if collection.locked:
        return 409, {"error": "Collection is locked"}

    summary = collection_remove_images_from_isic_ids(
        user=request.user,
        collection=collection,
        isic_ids=payload.isic_ids,
    )

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request,
        messages.INFO,
        f"Removed {len(summary['succeeded'])} images. It may take some time for counts to be updated.",  # noqa: E501
    )

    return JsonResponse(summary)
