from collections.abc import Generator
from datetime import UTC, datetime
from itertools import batched
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import BadRequest, ValidationError
from django.core.paginator import Paginator
from django.db.models import F
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls.base import reverse
from ninja.errors import ValidationError as NinjaValidationError
import pydantic

from isic.core.forms.collection import CollectionForm
from isic.core.models import Collection
from isic.core.pagination import CursorPagination, qs_with_hardcoded_count
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.services import image_metadata_csv
from isic.core.services.collection import create_collection, update_collection
from isic.core.utils.csv import EscapingDictWriter
from isic.core.utils.http import Echo
from isic.ingest.models import Contributor


@login_required
def collection_create(request):
    context = {}

    if request.method == "POST":
        context["form"] = CollectionForm(request.POST)
        if context["form"].is_valid():
            collection = create_collection(
                creator=request.user, **context["form"].cleaned_data, locked=False
            )
            return HttpResponseRedirect(reverse("core/collection-detail", args=[collection.pk]))
    else:
        context["form"] = CollectionForm()

    return render(
        request,
        "core/collection_create_or_edit.html",
        context,
    )


@needs_object_permission("core.edit_collection", (Collection, "pk", "pk"))
def collection_edit(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    form = CollectionForm(
        request.POST or {key: getattr(collection, key) for key in ["name", "description", "public"]}
    )

    if request.method == "POST" and form.is_valid():
        try:
            update_collection(collection, **form.cleaned_data)
        except ValidationError as e:
            messages.add_message(request, messages.ERROR, e.message)
        else:
            return HttpResponseRedirect(reverse("core/collection-detail", args=[collection.pk]))

    return render(
        request,
        "core/collection_create_or_edit.html",
        {"form": form, "collection": collection},
    )


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
def collection_download_metadata(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    qs = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.all(),
    )

    def csv_rows() -> Generator[bytes]:
        collection_metadata = image_metadata_csv(qs=qs)
        writer = EscapingDictWriter(Echo(), next(collection_metadata))
        yield writer.writeheader()

        # yield rows in batches, since responding with many small chunks incurs per-chunk
        # overhead in the WSGI write path and socket writes.
        for metadata_rows in batched(collection_metadata, 256, strict=False):
            chunk: list[bytes] = []
            for metadata_row in metadata_rows:
                assert isinstance(metadata_row, dict)  # noqa: S101
                chunk.append(writer.writerow(metadata_row))
            yield b"".join(chunk)

    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    response = StreamingHttpResponse(csv_rows(), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{slugify(collection.name)}_metadata_{current_time}.csv"'
    )

    return response


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
@needs_object_permission("core.create_doi", (Collection, "pk", "pk"))
def collection_create_doi(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    context: dict[str, Any] = {
        "collection": collection,
        "error": None,
    }

    if hasattr(collection, "doi") or hasattr(collection, "draftdoi"):
        return HttpResponseRedirect(
            reverse(
                "core/doi-detail",
                args=[
                    collection.doi.slug if hasattr(collection, "doi") else collection.draftdoi.slug
                ],
            )
        )
    elif not collection.images.exists():
        context["error"] = "A DOI cannot be created for an empty collection."

    return render(
        request,
        "core/collection_create_doi.html",
        context,
    )


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
def collection_detail(request, pk):
    collection = get_object_or_404(
        Collection.objects.select_related("cached_counts", "creator", "draftdoi", "doi"), pk=pk
    )

    # TODO: if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.select_related("accession").order_by("created").distinct(),
    )

    # prevent the paginator from doing a slow count.
    if hasattr(collection, "cached_counts"):
        images = qs_with_hardcoded_count(images, ("created",), collection.cached_counts.image_count)

    paginator = CursorPagination(ordering=("created",))
    try:
        cursor_input = CursorPagination.Input(
            limit=request.GET.get("limit", 30), cursor=request.GET.get("cursor")
        )
        page = paginator.paginate_queryset(images, pagination=cursor_input, request=request)
    except (pydantic.ValidationError, NinjaValidationError) as e:
        raise BadRequest("Invalid pagination parameters.") from e

    contributors = get_visible_objects(
        request.user,
        "ingest.view_contributor",
        Contributor.objects.filter(
            pk__in=collection.images.values("accession__cohort__contributor__pk").distinct()
        ).order_by("institution_name"),
    )

    image_removal_mode = (
        request.GET.get("image_removal_mode")
        and not collection.locked
        and request.user.has_perm("core.edit_collection", collection)
    )

    return render(
        request,
        "core/collection_detail.html",
        {
            "collection": collection,
            "contributors": contributors,
            "images": page["results"],
            "page": page,
            "image_removal_mode": image_removal_mode,
            "show_shares": request.user.is_staff or request.user == collection.creator,
        },
    )


def collection_list(request: HttpRequest) -> HttpResponse:
    collections = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.select_related("cached_counts", "doi").prefetch_related(
            "doi__related_identifiers", "doi__supplemental_files"
        ),
    )

    magic_filter = request.GET.get("magic_filter", "exclude")
    pinned_filter = request.GET.get("pinned_filter", "all")
    exclude_empty = request.GET.get("exclude_empty", "1") == "1"

    if magic_filter == "only":
        collections = collections.magic()
    elif magic_filter == "exclude":
        collections = collections.regular()

    if exclude_empty:
        collections = collections.filter(cached_counts__image_count__gt=0)

    if pinned_filter == "only":
        collections = collections.filter(pinned=True)
    elif pinned_filter == "exclude":
        collections = collections.filter(pinned=False)

    sort = request.GET.get("sort", "name")
    order = request.GET.get("order", "asc")
    valid_sorts: set[str] = {"name", "created", "doi", "images"}

    if sort in valid_sorts:
        if sort == "doi":
            sort_expr = (
                F("doi__id").desc(nulls_last=True)
                if order == "desc"
                else F("doi__id").asc(nulls_last=True)
            )
            collections = collections.order_by(sort_expr)
        elif sort == "images":
            sort_expr = (
                F("cached_counts__image_count").desc(nulls_last=True)
                if order == "desc"
                else F("cached_counts__image_count").asc(nulls_last=True)
            )
            collections = collections.order_by(sort_expr)
        else:
            order_field = f"-{sort}" if order == "desc" else sort
            collections = collections.order_by(order_field)

    paginator = Paginator(collections, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/collection_list.html",
        {
            "page": page,
            "current_sort": sort,
            "current_order": order,
            "magic_filter": magic_filter,
            "pinned_filter": pinned_filter,
            "exclude_empty": exclude_empty,
        },
    )
