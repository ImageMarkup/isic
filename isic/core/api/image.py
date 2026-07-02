from typing import Any

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Max, Q
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from isic_metadata import FIELD_REGISTRY
from ninja import Field, ModelSchema, Query, Router, Schema
from ninja.pagination import paginate
from pyparsing.exceptions import ParseException
from sentry_sdk import set_tag

from isic.auth import is_authenticated
from isic.core.models import Image
from isic.core.pagination import CursorPagination, qs_with_hardcoded_count
from isic.core.permissions import get_visible_objects
from isic.core.search import facets, get_elasticsearch_client
from isic.core.serializers import SearchQueryIn
from isic.types import AuthenticatedHttpRequest

router = Router()

default_qs = Image.objects.select_related("accession__cohort").distinct()


class ImageSearchParseError(Exception):
    pass


class FileOut(Schema):
    url: str
    size: int


class ImageFilesOut(Schema):
    full: FileOut
    thumbnail_256: FileOut


class ImageOut(ModelSchema):
    class Meta:
        model = Image
        fields = ["public"]

    isic_id: str = Field(alias="isic_id")
    copyright_license: str = Field(alias="accession.copyright_license")
    attribution: str = Field(alias="accession.cohort.default_attribution")
    files: ImageFilesOut
    metadata: dict

    @staticmethod
    def resolve_files(image: Image) -> ImageFilesOut:
        full_url = image.blob.url
        thumbnail_url = image.thumbnail_256.url
        full_size = image.accession.blob_size
        thumbnail_size = image.accession.thumbnail_256_size

        return ImageFilesOut(
            full=FileOut(url=full_url, size=full_size),
            thumbnail_256=FileOut(url=thumbnail_url, size=thumbnail_size),
        )

    @staticmethod
    def resolve_metadata(image: Image) -> dict:
        metadata: dict[str, dict[str, Any]] = {
            "acquisition": {"pixels_x": image.accession.width, "pixels_y": image.accession.height},
            "clinical": {},
        }

        for key, value in image.metadata.items():
            try:
                metadata[FIELD_REGISTRY[key].type][key] = value  # type: ignore[index]
            except KeyError:
                # it's probably a computed field
                for computed_field in image.accession.computed_fields:
                    if key in computed_field.output_field_names:
                        metadata[computed_field.type][key] = value
                        break
                else:
                    raise

        return metadata


class PinnedFirstPagination(CursorPagination):
    # Subclass of CursorPagination with custom behavior to allow ordering by multiple fields
    # If query contains "pin_sort=true", return pinned images first, then sort by created.
    #
    # NOTE: Django Ninja has its own CursorPagination implementation upstream
    # (https://github.com/vitalik/django-ninja/pull/1657), but it only derives the cursor
    # position and the seek (__gt/__lt) filter from the FIRST ordering field -- any
    # additional ordering fields affect ORDER BY only, not the keyset comparison. That
    # makes it incorrect for paging across more than one field (e.g. "-pinned", "created"):
    # rows tied on the first field aren't disambiguated by the rest. _apply_ordering and
    # _get_position_from_instance are overridden below to build the position and the
    # predicate from *all* ordering fields.

    def _apply_ordering(self, queryset, cursor, order):
        """
        Filter ``queryset`` down to the rows that fall *after* the cursor position.

        This is the multi-field generalization of the keyset/seek predicate. The
        cursor encodes one value per ordering field (joined by "|"), and we need the
        SQL equivalent of a lexicographic tuple comparison against that position.
        For ordering ``(-pinned, created, id)`` (pinned descending, the rest
        ascending) paging forward, "after" the cursor row
        ``(pinned=P, created=C, id=I)`` means::

            pinned < P
            OR (pinned = P AND created > C)
            OR (pinned = P AND created = C AND id > I)

        It's expanded by hand into this OR-of-ANDs rather than using a SQL row-value
        constructor (``(pinned, created, id) > (P, C, I)``) because row-value
        comparison can't express per-field ascending/descending directions, which
        keyset pagination requires (here ``pinned`` descends while ``created`` and
        ``id`` ascend).

        Each ordering field contributes one OR term: a strict comparison on that
        field (``__gt``/``__lt``, flipped for descending fields and for reverse
        cursor across an ordering change) raises ``ValueError``.
        """
        if cursor.position is not None:
            position_values = cursor.position.split("|")
            if len(position_values) != len(order):
                # The cursor was built for a different ordering than this request
                # (e.g. pin_sort was toggled).
                raise ValueError("Cursor position does not match the current ordering.")

            field_names = [field.lstrip("-") for field in order]
            q_obj = Q()
            for i, field in enumerate(order):
                is_reversed = field.startswith("-")
                comparison = "__gt" if cursor.reverse == is_reversed else "__lt"
                # Strict comparison on field i AND equality on every field before it.
                field_condition = Q(**{f"{field_names[i]}{comparison}": position_values[i]})
                for j in range(i):
                    field_condition &= Q(**{field_names[j]: position_values[j]})

                q_obj |= field_condition
            queryset = queryset.filter(q_obj)
        return queryset

    def _get_position_from_instance(self, instance, ordering):
        values = []
        for field in ordering:
            fname = field.lstrip("-")
            attr = instance[fname] if isinstance(instance, dict) else getattr(instance, fname)
            values.append(str(attr))
        return "|".join(values)

    def paginate_queryset(self, queryset, pagination, request, **params):
        if request.GET.get("pin_sort"):
            queryset = queryset.order_by("pinned", "created")
        else:
            queryset = queryset.order_by("created")
        return super().paginate_queryset(queryset, pagination, request, **params)


@router.get(
    "/", response=list[ImageOut], summary="Return a list of images.", include_in_schema=True
)
@paginate(PinnedFirstPagination)
def image_list(request: HttpRequest):
    qs = get_visible_objects(request.user, "core.view_image", default_qs)

    if settings.ISIC_USE_ELASTICSEARCH_COUNTS:
        es_query = SearchQueryIn().to_es_query(request.user)
        es_count = get_elasticsearch_client().count(
            index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
            body={"query": es_query},
        )["count"]
        return qs_with_hardcoded_count(qs, Image._meta.ordering, es_count)

    return qs


@router.get(
    "/search/",
    response={200: list[ImageOut], 400: dict},
    summary="Search images with a key:value query string.",
    description=render_to_string("core/swagger_image_search_description.html"),
    include_in_schema=True,
)
@paginate(PinnedFirstPagination)
def image_search(request: HttpRequest, search: SearchQueryIn = Query(...)):
    try:
        qs = search.to_queryset(user=request.user, qs=default_qs)
        if settings.ISIC_USE_ELASTICSEARCH_COUNTS:
            es_query = search.to_es_query(request.user)
    except ParseException as e:
        # Normally we'd like this to be handled by the input serializer validation, but
        # for backwards compatibility we must return 400 rather than 422.
        # The pagination wrapper means we can't just return the response we'd like from here.
        # The handler for this exception type is defined in urls.py.
        raise ImageSearchParseError from e
    else:
        if settings.ISIC_USE_ELASTICSEARCH_COUNTS:
            es_count = get_elasticsearch_client().count(
                index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
                body={"query": es_query},
            )["count"]
            return qs_with_hardcoded_count(qs, Image._meta.ordering, es_count)

        return qs


@router.get(
    "/search/size/",
    response={200: dict, 400: dict},
    summary="Get total size of images matching a search query.",
    include_in_schema=False,
)
def image_search_size(request: HttpRequest, search: SearchQueryIn = Query(...)):
    try:
        es_query = search.to_es_query(request.user)
    except ParseException as e:
        raise ImageSearchParseError from e

    body = {
        "size": 0,
        "aggs": {"total_size": {"sum": {"field": "blob_size"}}},
        "query": es_query,
    }

    result = get_elasticsearch_client().search(
        index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
        body=body,
    )

    total_size = result["aggregations"]["total_size"]["value"] or 0
    return {"size": int(total_size)}


@router.get("/facets/", response=dict, include_in_schema=False)
def image_facets(request: HttpRequest, search: SearchQueryIn = Query(...)):
    cache_key = f"image_facets:{search.to_cache_key(request.user)}"
    cached_facets = cache.get(cache_key)

    set_tag("cached_facets", cached_facets is not None)

    if cached_facets:
        return cached_facets

    try:
        query = search.to_es_query(request.user)
    except ParseException as e:
        raise ImageSearchParseError from e

    ret = facets(query)
    cache.set(cache_key, ret, 86400)
    return ret


@router.get(
    "/{isic_id}/",
    response=ImageOut,
    summary="Retrieve a single image by ISIC ID.",
    include_in_schema=True,
)
def image_detail(request: HttpRequest, isic_id: str):
    qs = get_visible_objects(request.user, "core.view_image", default_qs)
    return get_object_or_404(qs, isic_id=isic_id)


class SimilarImageOut(ImageOut):
    distance: float


@router.get(
    "/{isic_id}/similar/",
    response=list[SimilarImageOut],
    summary="Find images similar to the specified image.",
    include_in_schema=True,
    auth=is_authenticated,
)
def image_similar(
    request: AuthenticatedHttpRequest, isic_id: str, limit: int = Query(10, le=50)
) -> list[SimilarImageOut]:
    qs = get_visible_objects(request.user, "core.view_image", default_qs)
    image = get_object_or_404(qs, isic_id=isic_id)

    if not image.has_embedding:
        return []

    similar_qs = image.similar_images().select_related("accession__cohort")
    similar_qs = get_visible_objects(request.user, "core.view_image", similar_qs)
    return similar_qs[:limit]


class SetPinned(Schema):
    pinned: bool

    model_config = {"extra": "forbid"}


@router.post(
    "/{id}/set-pinned/",
    response={200: None, 400: dict, 403: dict},
    include_in_schema=False,
)
def image_set_pinned(request, id: int, payload: SetPinned):
    if not request.user.is_staff:
        return 403, {"error": "You do not have permission to pin or unpin this image."}

    qs = get_visible_objects(request.user, "core.view_image", Image.objects.all())
    image = get_object_or_404(qs.distinct(), id=id)
    if payload.pinned:
        last_pin = Image.objects.aggregate(Max("pinned")).get("pinned__max") or 0
        image.pinned = last_pin + 1
    else:
        image.pinned = None
    image.save()
    action = "pinned" if payload.pinned else "unpinned"
    messages.add_message(request, messages.SUCCESS, f"Image {action}.")
    return 200, None
