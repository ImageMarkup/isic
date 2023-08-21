from django.conf import settings
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from isic_metadata import FIELD_REGISTRY
from ninja import Field, ModelSchema, Query, Router, Schema
from ninja.pagination import paginate
from pyparsing.exceptions import ParseException

from isic.core.dsl import parse_query
from isic.core.models import Collection, Image
from isic.core.pagination import CursorPagination
from isic.core.permissions import get_visible_objects
from isic.core.search import build_elasticsearch_query, facets
from isic.core.serializers import SearchQueryIn

router = Router()

# TODO this originally had "distinct()" on it; I don't think that's needed though
default_qs = Image.objects.select_related("accession__cohort").defer(
    "accession__unstructured_metadata"
)


class ImageSearchParseError(Exception):
    pass


class FileOut(Schema):
    url: str
    size: int


class ImageFilesOut(Schema):
    full: FileOut
    thumbnail_256: FileOut


class ImageOut(ModelSchema):
    class Config:
        model = Image
        model_fields = ["public"]

    isic_id: str = Field(alias="isic_id")
    copyright_license: str = Field(alias="accession.copyright_license")
    attribution: str = Field(alias="accession.cohort.attribution")
    files: ImageFilesOut
    metadata: dict

    @staticmethod
    def resolve_files(image: Image) -> dict:
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
        metadata = {
            "acquisition": {"pixels_x": image.accession.width, "pixels_y": image.accession.height},
            "clinical": {},
        }

        for key, value in image.accession.redacted_metadata.items():
            # this is the only field that we expose that isn't in the FIELD_REGISTRY
            # since it's a derived field.
            if key == "age_approx":
                metadata["clinical"][key] = value
            else:
                metadata[FIELD_REGISTRY[key]["type"]][key] = value

        return metadata


@router.get("/", response=list[ImageOut], summary="Return a list of images.")
@paginate(CursorPagination)
def list_images(request: HttpRequest):
    return get_visible_objects(request.user, "core.view_image", default_qs)


@router.get(
    "/search/",
    response={200: list[ImageOut], 400: dict},
    summary="Search images with a key:value query string.",
    description=render_to_string("core/swagger_image_search_description.html"),
)
@paginate(CursorPagination)
def search_images(request: HttpRequest, search: SearchQueryIn = Query(...)):  # noqa: B008
    try:
        return search.to_queryset(user=request.user, qs=default_qs)
    except ParseException:
        # Normally we'd like this to be handled by the input serializer validation, but
        # for backwards compatibility we must return 400 rather than 422.
        # The pagination wrapper means we can't just return the response we'd like from here.
        # The handler for this exception type is defined in urls.py.
        raise ImageSearchParseError()


@router.get("/facets/", response=dict, include_in_schema=False)
def get_facets(request: HttpRequest, search: SearchQueryIn = Query(...)):  # noqa: B008
    if search.query:
        try:
            parse_query(search.query)
        except ParseException:
            raise ImageSearchParseError()

    query = build_elasticsearch_query(
        search.query or "",
        request.user,
        search.collections,
    )
    # Manually pass the list of visible collection PKs through so buckets with
    # counts of 0 aren't included in the facets output for non-visible collections.
    collection_pks = list(
        get_visible_objects(
            request.user,
            "core.view_collection",
            Collection.objects.values_list("pk", flat=True),
        )
    )
    return facets(query, collection_pks)


@router.get("/{isic_id}/", response=ImageOut, summary="Retrieve a single image by ISIC ID.")
def retrieve_image(request: HttpRequest, isic_id: str):
    qs = get_visible_objects(request.user, "core.view_image", default_qs)
    return get_object_or_404(qs, isic_id=isic_id)
