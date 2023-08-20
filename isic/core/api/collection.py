from django.contrib import messages
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Field, ModelSchema, Router, Schema
from ninja.pagination import paginate
from pydantic.types import conlist, constr

from isic.core.constants import ISIC_ID_REGEX
from isic.core.models.collection import Collection
from isic.core.pagination import CursorPagination
from isic.core.permissions import get_visible_objects
from isic.core.serializers import SearchQueryIn
from isic.core.services.collection.image import (
    collection_add_images_from_isic_ids,
    collection_remove_images_from_isic_ids,
)
from isic.core.tasks import populate_collection_from_search_task

router = Router()


class CollectionOut(ModelSchema):
    class Config:
        model = Collection
        model_fields = ["id", "name", "description", "public", "pinned", "locked", "doi"]

    doi_url: str | None = Field(alias="doi_url")


@router.get("/", response=list[CollectionOut], summary="Return a list of collections.")
@paginate(CursorPagination)
def collection_list(request, pinned: bool | None = None) -> list[CollectionOut]:
    queryset = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    if pinned is not None:
        queryset = queryset.filter(pinned=pinned)
    return queryset


@router.get("/{id}/", response=CollectionOut, summary="Retrieve a single collection by ID.")
def collection_detail(request, id: int) -> CollectionOut:
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs, id=id)
    return collection


@router.post(
    "/{id}/populate-from-search/",
    response={202: None, 403: dict, 409: dict},
    include_in_schema=False,
)
def collection_populate_from_search(request, id: int, payload: SearchQueryIn):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs, id=id)

    if not request.user.has_perm("core.add_images", collection):
        return 403, {"error": "You do not have permission to add images to this collection."}

    if collection.locked:
        return 409, {"error": "Collection is locked"}

    if collection.public and payload.to_queryset(request.user).private().exists():
        return 409, {"error": "Collection is public and cannot contain private images."}

    # Pass data instead of validated_data because the celery task is going to revalidate.
    # This avoids re encoding collections as a comma delimited string.
    populate_collection_from_search_task.delay(id, request.user.pk, payload.dict())

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request, messages.INFO, "Adding images to collection, this may take a few minutes."
    )
    return 202, {}


class IsicIdList(Schema):
    isic_ids: conlist(constr(pattern=ISIC_ID_REGEX), max_length=500)


# TODO: refactor *-from-list methods
@router.post(
    "/{id}/populate-from-list/", response={200: None, 403: dict, 409: dict}, include_in_schema=False
)
def collection_populate_from_list(request, id, payload: IsicIdList):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs, id=id)

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
    collection = get_object_or_404(qs, id=id)

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
    messages.add_message(request, messages.INFO, f'Removed {len(summary["succeeded"])} images.')

    return JsonResponse(summary)
