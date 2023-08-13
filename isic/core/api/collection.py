from django.contrib import messages
from django.db.models.query import QuerySet
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import ModelSchema, Router, Schema
from ninja.pagination import paginate
from pydantic.types import conlist, constr

from isic.core.constants import ISIC_ID_REGEX
from isic.core.models.collection import Collection
from isic.core.models.image import Image
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

    doi_url: str | None

    @staticmethod
    def resolve_doi_url(obj: Collection):
        return obj.doi_url


@router.get("/", response=list[CollectionOut])
@paginate(CursorPagination)
def collection_list(request, pinned: bool | None = None) -> list[CollectionOut]:
    queryset = Collection.objects.all()
    if pinned is not None:
        queryset = queryset.filter(pinned=pinned)
    return queryset


# TODO: permissions filter


@router.get("/{id}", response=CollectionOut)
def collection_detail(request, id) -> CollectionOut:
    collection = get_object_or_404(Collection, id=id)
    return collection


@router.post("/{id}/populate-from-search/", response={202: None, 403: dict, 409: dict})
def collection_populate_from_search(request, id, payload: SearchQueryIn):
    collection = get_object_or_404(Collection, id=id)

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

    def to_queryset(self, user, qs: QuerySet[Image] | None = None) -> QuerySet[Image]:
        qs = qs if qs is not None else Image._default_manager.all()
        qs = qs.filter(isic_id__in=self.isic_ids)
        return get_visible_objects(user, "core.view_image", qs)


# TODO: refactor *-from-list methods
@router.post("/{id}/populate-from-list/", response={200: None, 403: dict, 409: dict})
def collection_populate_from_list(request, id, payload: IsicIdList):
    collection = get_object_or_404(Collection, id=id)

    if not request.user.has_perm("core.add_images", collection):
        return 403, {"error": "You do not have permission to add images to this collection."}

    if collection.locked:
        return 409, {"error": "Collection is locked"}

    summary = collection_add_images_from_isic_ids(
        user=request.user,
        collection=collection,
        isic_ids=payload.to_queryset(request.user).values_list("isic_id", flat=True),
    )

    return JsonResponse(summary)


@router.post("/{id}/remove-from-list/", response={200: None, 403: dict, 409: dict})
def remove_from_list(request, id, payload: IsicIdList):
    collection = get_object_or_404(Collection, id=id)

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
