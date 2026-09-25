from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.urls import path
from jaro import jaro_winkler_metric
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from isic.auth import IsAuthenticated, IsStaff, ReadOnly
from isic.core.constants import ISIC_ID_REGEX
from isic.core.models.collection import Collection
from isic.core.pagination import paginate
from isic.core.permissions import get_visible_objects
from isic.core.serializers import SearchQueryBodySerializer, StrictSerializer
from isic.core.services.collection import create_collection, delete_collection, update_collection
from isic.core.services.collection.image import (
    add_collection_images_from_isic_ids,
    remove_collection_images_from_isic_ids,
)
from isic.core.tasks import (
    populate_collection_from_isic_ids_task,
    populate_collection_from_search_task,
    share_collection_with_users_task,
)
from isic.ingest.models.accession import Accession


class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ["id", "name", "description", "public", "pinned", "locked", "doi", "doi_url"]

    doi = serializers.CharField(source="doi.id")
    doi_url = serializers.CharField(source="doi.external_url")


class CollectionListParamsSerializer(serializers.Serializer):
    pinned = serializers.BooleanField(allow_null=True, default=None)
    sort = serializers.ChoiceField(choices=["name", "created"], allow_null=True, default=None)


@api_view(["GET"])
@permission_classes([AllowAny])
def collection_list(request):
    params = CollectionListParamsSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    queryset = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())

    if params.validated_data["pinned"] is not None:
        queryset = queryset.filter(pinned=params.validated_data["pinned"])

    if params.validated_data["sort"] is not None:
        queryset = queryset.order_by(params.validated_data["sort"])

    return paginate(request, queryset, CollectionSerializer)


def isic_ids_field(**kwargs) -> serializers.ListField:
    return serializers.ListField(
        child=serializers.RegexField(ISIC_ID_REGEX, trim_whitespace=False), **kwargs
    )


class CreateCollectionFromIsicIdsSerializer(StrictSerializer):
    name = serializers.CharField(allow_blank=True, trim_whitespace=False)
    description = serializers.CharField(default="", allow_blank=True, trim_whitespace=False)
    isic_ids = isic_ids_field(min_length=1)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def collection_create_from_isic_ids(request):
    payload = CreateCollectionFromIsicIdsSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    isic_ids = payload.validated_data["isic_ids"]

    new_collection = create_collection(
        creator=request.user,
        name=payload.validated_data["name"],
        description=payload.validated_data["description"],
        public=False,
        locked=False,
    )

    populate_collection_from_isic_ids_task.delay_on_commit(
        new_collection.pk, request.user.pk, isic_ids
    )

    messages.add_message(
        request,
        messages.INFO,
        f"Created collection '{new_collection.name}'. Adding {len(isic_ids)} images, this may take a few minutes.",  # noqa: E501
    )

    return Response({"collection_id": new_collection.pk}, status=status.HTTP_202_ACCEPTED)


# See also isic.find.api.QuerySerializer
class AutocompleteQuerySerializer(serializers.Serializer):
    query = serializers.CharField(allow_blank=True, trim_whitespace=False)

    def validate_query(self, value: str) -> str:
        if len(value) < 3:
            raise serializers.ValidationError("Query too short.")
        return value


@api_view(["GET"])
@permission_classes([AllowAny])
def collection_autocomplete(request):
    params = AutocompleteQuerySerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    query = params.validated_data["query"]

    qs = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.select_related("doi").filter(name__icontains=query, locked=False),
    )

    if not request.user.is_staff and request.user.is_authenticated:
        qs = qs.filter(creator=request.user)

    # sort by jaro winkler, then name to make something like "challenge" return the
    # challenge collections in order.
    collections = sorted(
        qs,
        key=lambda collection: (
            -jaro_winkler_metric(collection.name.upper(), query.upper()),
            collection.name,
        ),
    )

    return Response(CollectionSerializer(collections[:20], many=True).data)


class SharingInfoParamsSerializer(serializers.Serializer):
    collection_ids = serializers.ListField(child=serializers.IntegerField())


@api_view(["GET"])
@permission_classes([IsStaff])
def collection_sharing_info(request):
    params = SharingInfoParamsSerializer(data=request.query_params)
    params.is_valid(raise_exception=True)
    collections = (
        Collection.objects.filter(id__in=params.validated_data["collection_ids"])
        .select_related("creator")
        .prefetch_related("shares")
    )

    def display_name(user):
        return user.get_full_name() or user.email

    return Response(
        [
            {
                "id": collection.id,
                "name": collection.name,
                "public": collection.public,
                "owner": {
                    "id": collection.creator.id,
                    "name": display_name(collection.creator),
                },
                "shared_with": [
                    {"id": u.id, "name": display_name(u)} for u in collection.shared_with
                ],
            }
            for collection in collections
        ]
    )


@api_view(["GET", "DELETE"])
@permission_classes([ReadOnly | IsAuthenticated])
def collection_detail(request, id: int):
    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if request.method == "GET":
        return Response(CollectionSerializer(collection).data)

    if not request.user.has_perm("core.edit_collection", collection):
        return Response(
            {"error": "You do not have permission to delete this collection."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        delete_collection(collection=collection)
    except ValidationError as e:
        return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)

    return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionShareSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField())
    notify = serializers.BooleanField(default=True)


@api_view(["POST"])
@permission_classes([IsStaff])
def collection_share_to_users(request, id: int):
    payload = CollectionShareSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    user_ids = payload.validated_data["user_ids"]
    notify = payload.validated_data["notify"]

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if collection.is_magic:
        return Response(
            {"error": "Magic collections cannot be shared."}, status=status.HTTP_400_BAD_REQUEST
        )

    if any(user_id == request.user.id for user_id in user_ids):
        return Response(
            {"error": "Cannot share a collection with yourself."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    share_collection_with_users_task.delay_on_commit(
        collection.id, request.user.id, user_ids, notify=notify
    )

    if notify:
        msg = "Sharing collection with user(s) and notifying them via email, this may take a few minutes."  # noqa: E501
    else:
        msg = "Sharing collection with user(s), this may take a few minutes."
    messages.add_message(request, messages.INFO, msg)

    return Response(status=status.HTTP_202_ACCEPTED)


@api_view(["GET"])
@permission_classes([AllowAny])
def collection_attribution_information(request, id: int):
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

    return Response([{"license": x[0], "attribution": x[1], "count": x[2]} for x in counts])


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def collection_populate_from_search(request, id: int):
    payload = SearchQueryBodySerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.add_images", collection):
        return Response(
            {"error": "You do not have permission to add images to this collection."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if collection.locked:
        return Response({"error": "Collection is locked"}, status=status.HTTP_409_CONFLICT)

    if collection.public and payload.to_queryset(request.user).private().exists():
        return Response(
            {"error": "Collection is public and cannot contain private images."},
            status=status.HTTP_409_CONFLICT,
        )

    populate_collection_from_search_task.delay_on_commit(
        id, request.user.pk, dict(payload.validated_data)
    )

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request, messages.INFO, "Adding images to collection, this may take a few minutes."
    )
    return Response(status=status.HTTP_202_ACCEPTED)


class PopulateCollectionFromIsicIdsSerializer(StrictSerializer):
    isic_ids = isic_ids_field(min_length=1)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def collection_populate_from_isic_ids(request, id: int):
    payload = PopulateCollectionFromIsicIdsSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    isic_ids = payload.validated_data["isic_ids"]

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.add_images", collection):
        return Response(
            {"error": "You do not have permission to add images to this collection."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if collection.locked:
        return Response({"error": "Collection is locked"}, status=status.HTTP_409_CONFLICT)

    populate_collection_from_isic_ids_task.delay_on_commit(collection.pk, request.user.pk, isic_ids)

    messages.add_message(
        request,
        messages.INFO,
        f"Adding {len(isic_ids)} images to '{collection.name}', this may take a few minutes.",
    )

    return Response(status=status.HTTP_202_ACCEPTED)


class SetPinnedSerializer(StrictSerializer):
    pinned = serializers.BooleanField()


@api_view(["POST"])
@permission_classes([IsStaff])
def collection_set_pinned(request, id: int):
    payload = SetPinnedSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    pinned = payload.validated_data["pinned"]

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    try:
        update_collection(collection=collection, ignore_lock=True, pinned=pinned)
    except ValidationError as e:
        error = "; ".join(e.messages)
        messages.add_message(request, messages.ERROR, error)
        return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

    action = "pinned" if pinned else "unpinned"
    messages.add_message(request, messages.SUCCESS, f"Collection {action}.")
    return Response(status=status.HTTP_200_OK)


class IsicIdListSerializer(StrictSerializer):
    isic_ids = isic_ids_field(max_length=500)


# TODO: refactor *-from-list methods
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def collection_populate_from_list(request, id: int):
    payload = IsicIdListSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.add_images", collection):
        return Response(
            {"error": "You do not have permission to add images to this collection."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if collection.locked:
        return Response({"error": "Collection is locked"}, status=status.HTTP_409_CONFLICT)

    summary = add_collection_images_from_isic_ids(
        user=request.user,
        collection=collection,
        isic_ids=payload.validated_data["isic_ids"],
    )

    return Response(summary)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def collection_remove_from_list(request, id: int):
    payload = IsicIdListSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    qs = get_visible_objects(request.user, "core.view_collection", Collection.objects.all())
    collection = get_object_or_404(qs.distinct(), id=id)

    if not request.user.has_perm("core.remove_images", collection):
        return Response(
            {"error": "You do not have permission to add images to this collection."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if collection.locked:
        return Response({"error": "Collection is locked"}, status=status.HTTP_409_CONFLICT)

    summary = remove_collection_images_from_isic_ids(
        user=request.user,
        collection=collection,
        isic_ids=payload.validated_data["isic_ids"],
    )

    # TODO: this is a weird mixture of concerns between SSR and an API, figure out a better
    # way to handle this.
    messages.add_message(
        request,
        messages.INFO,
        f"Removed {len(summary['succeeded'])} images. It may take some time for counts to be updated.",  # noqa: E501
    )

    return Response(summary)


urlpatterns = [
    path("", collection_list, name="collection_list"),
    path(
        "create-from-isic-ids/",
        collection_create_from_isic_ids,
        name="collection_create_from_isic_ids",
    ),
    path("autocomplete/", collection_autocomplete, name="collection_autocomplete"),
    path("sharing-info/", collection_sharing_info, name="collection_sharing_info"),
    path("<int:id>/", collection_detail, name="collection_detail"),
    path("<int:id>/", collection_detail, name="collection_delete"),
    path("<int:id>/share/", collection_share_to_users, name="collection_share_to_users"),
    path(
        "<int:id>/attribution/",
        collection_attribution_information,
        name="collection_attribution_information",
    ),
    path(
        "<int:id>/populate-from-search/",
        collection_populate_from_search,
        name="collection_populate_from_search",
    ),
    path(
        "<int:id>/populate-from-isic-ids/",
        collection_populate_from_isic_ids,
        name="collection_populate_from_isic_ids",
    ),
    path("<int:id>/set-pinned/", collection_set_pinned, name="collection_set_pinned"),
    path(
        "<int:id>/populate-from-list/",
        collection_populate_from_list,
        name="collection_populate_from_list",
    ),
    path(
        "<int:id>/remove-from-list/",
        collection_remove_from_list,
        name="collection_remove_from_list",
    ),
]
