from typing import Literal

from django.contrib import messages
from django.db.models import Count, Q
from django.http.response import JsonResponse
from django.shortcuts import get_object_or_404
from ninja import Field, ModelSchema, Router, Schema
from ninja.pagination import paginate
from pydantic.types import conlist, constr

from isic.core.constants import ISIC_ID_REGEX
from isic.core.models.base import CopyrightLicense
from isic.core.models.collection import Collection
from isic.core.pagination import CursorPagination
from isic.core.permissions import get_visible_objects
from isic.core.serializers import SearchQueryIn
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


class CollectionOut(ModelSchema):
    class Meta:
        model = Collection
        fields = ["id", "name", "description", "public", "pinned", "locked", "doi"]

    doi_url: str | None = Field(alias="doi_url")


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


@router.get(
    "/{id}/",
    response=CollectionOut,
    summary="Retrieve a single collection by ID.",
    include_in_schema=True,
)
def collection_detail(request, id: int) -> CollectionOut:
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    return get_object_or_404(qs, id=id)


class CollectionShareIn(Schema):
    user_ids: list[int]


@router.post("/{id}/share/", response={202: None, 404: dict, 403: dict}, include_in_schema=False)
def collection_share_to_users(request, id: int, payload: CollectionShareIn):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs, id=id)

    if not request.user.is_staff:
        return 403, {"error": "You do not have permission to share this collection."}

    share_collection_with_users_task.delay(  # nosem: require-delay-on-commit
        collection.id, request.user.id, payload.user_ids
    )

    messages.add_message(
        request, messages.INFO, "Sharing collection with user(s), this may take a few minutes."
    )

    return 202, {}


class CollectionLicenseBreakdown(Schema):
    license_counts: dict[str, int]


@router.get(
    "/{id}/licenses/",
    response=CollectionLicenseBreakdown,
    summary="Retrieve a breakdown of the licenses of the specified collection.",
    include_in_schema=False,
)
def collection_license_breakdown(request, id: int) -> CollectionLicenseBreakdown:
    qs = get_visible_objects(request.user, "core.view_collection")
    collection = get_object_or_404(qs, id=id)
    images = get_visible_objects(request.user, "core.view_image", collection.images.distinct())
    license_counts = (
        Accession.objects.filter(image__in=images)
        .values("copyright_license")
        .aggregate(
            **{
                license_: Count("copyright_license", filter=Q(copyright_license=license_))
                for license_ in CopyrightLicense.values
            }
        )
    )

    return {"license_counts": license_counts}


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
    populate_collection_from_search_task.delay(  # nosem: require-delay-on-commit
        id, request.user.pk, payload.dict()
    )

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request, messages.INFO, "Adding images to collection, this may take a few minutes."
    )
    return 202, {}


class IsicIdList(Schema):
    isic_ids: conlist(constr(pattern=ISIC_ID_REGEX), max_length=500)

    model_config = {"extra": "forbid"}


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
