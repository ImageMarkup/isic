from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from isic_metadata import FIELD_REGISTRY
from ninja import Field, ModelSchema, Query, Router, Schema
from ninja.pagination import paginate
from pyparsing.exceptions import ParseException

from isic.core.models import Collection, Image
from isic.core.pagination import CursorPagination, qs_with_hardcoded_count
from isic.core.permissions import get_visible_objects
from isic.core.search import facets, get_elasticsearch_client
from isic.core.serializers import SearchQueryIn
from isic.stats.models import SearchQuery

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
    attribution: str = Field(alias="accession.cohort.attribution")
    files: ImageFilesOut
    metadata: dict

    @staticmethod
    def resolve_files(image: Image) -> ImageFilesOut:
        if settings.ISIC_PLACEHOLDER_IMAGES:
            full_url = f"https://picsum.photos/seed/{image.id}/1000"
            thumbnail_url = f"https://picsum.photos/seed/{image.id}/256"
        else:
            full_url = image.accession.blob.url
            thumbnail_url = image.accession.thumbnail_256.url

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


@router.get(
    "/", response=list[ImageOut], summary="Return a list of images.", include_in_schema=True
)
@paginate(CursorPagination)
def list_images(request: HttpRequest):
    qs = get_visible_objects(request.user, "core.view_image", default_qs)

    if settings.ISIC_USE_ELASTICSEARCH_COUNTS:
        es_query = SearchQueryIn().to_es_query(request.user)
        es_count = get_elasticsearch_client().count(
            index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
            body={"query": es_query},
        )["count"]
        return qs_with_hardcoded_count(qs, es_count)

    return qs


@router.get(
    "/search/",
    response={200: list[ImageOut], 400: dict},
    summary="Search images with a key:value query string.",
    description=render_to_string("core/swagger_image_search_description.html"),
    include_in_schema=True,
)
@paginate(CursorPagination)
def search_images(request: HttpRequest, search: SearchQueryIn = Query(...)):
    try:
        if search.query:
            SearchQuery.objects.create(value=search.query)

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
            return qs_with_hardcoded_count(qs, es_count)

        return qs


@router.get("/facets/", response=dict, include_in_schema=False)
def get_facets(request: HttpRequest, search: SearchQueryIn = Query(...)):
    cache_key = f"get_facets:{search.to_cache_key(request.user)}"
    cached_facets = cache.get(cache_key)

    if cached_facets:
        return cached_facets

    try:
        query = search.to_es_query(request.user)
    except ParseException as e:
        raise ImageSearchParseError from e

    # Manually pass the list of visible collection PKs through so buckets with
    # counts of 0 aren't included in the facets output for non-visible collections.
    collection_pks = list(
        get_visible_objects(
            request.user,
            "core.view_collection",
            Collection.objects.values_list("pk", flat=True),
        )
    )

    ret = facets(query, collection_pks)
    cache.set(cache_key, ret, 86400)
    return ret


@router.get(
    "/{isic_id}/",
    response=ImageOut,
    summary="Retrieve a single image by ISIC ID.",
    include_in_schema=True,
)
def retrieve_image(request: HttpRequest, isic_id: str):
    qs = get_visible_objects(request.user, "core.view_image", default_qs)
    return get_object_or_404(qs, isic_id=isic_id)
