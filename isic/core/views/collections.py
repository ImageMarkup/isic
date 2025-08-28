from collections.abc import Iterable
from datetime import UTC, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query_utils import Q
from django.http import StreamingHttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls.base import reverse

from isic.core.filters import CollectionFilter
from isic.core.forms.collection import CollectionForm
from isic.core.models import Collection
from isic.core.pagination import CursorPagination, qs_with_hardcoded_count
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.services import image_metadata_csv
from isic.core.services.collection import collection_create, collection_update
from isic.core.utils.csv import EscapingDictWriter
from isic.core.utils.http import Buffer
from isic.ingest.models import Contributor


def collection_list(request):
    # TODO: should the image count be access controlled too?
    collections = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.select_related("cohort", "cached_counts").order_by("-pinned", "name"),
    )

    if request.user.is_authenticated:
        counts = collections.aggregate(
            pinned=Count("pk", filter=Q(pinned=True)),
            doi=Count("pk", filter=Q(doi__isnull=False)),
            shared_with_me=Count("pk", filter=Q(shares=request.user)),
            mine=Count("pk", filter=Q(creator=request.user)),
            all_=Count("pk"),
        )
    else:
        counts = collections.aggregate(
            pinned=Count("pk", filter=Q(pinned=True)),
            doi=Count("pk", filter=Q(doi__isnull=False)),
            all_=Count("pk"),
        )

    filter_ = CollectionFilter(request.GET, queryset=collections, user=request.user)
    paginator = Paginator(filter_.qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/collection_list.html",
        {"collections": page, "filter": filter_, "counts": counts},
    )


@login_required
def collection_create_(request):
    context = {}

    if request.method == "POST":
        context["form"] = CollectionForm(request.POST)
        if context["form"].is_valid():
            collection = collection_create(
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
            collection_update(collection, **form.cleaned_data)
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

    def csv_rows(buffer: Buffer) -> Iterable[bytes]:
        collection_metadata = image_metadata_csv(qs=qs)
        writer = EscapingDictWriter(buffer, next(collection_metadata))
        yield writer.writeheader()

        for metadata_row in collection_metadata:
            assert isinstance(metadata_row, dict)  # noqa: S101
            yield writer.writerow(metadata_row)

    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    response = StreamingHttpResponse(csv_rows(Buffer()), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{slugify(collection.name)}_metadata_{current_time}.csv"'
    )

    return response


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
@needs_object_permission("core.create_doi", (Collection, "pk", "pk"))
def collection_create_doi_(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    context = {
        "collection": collection,
        "error": None,
    }

    if hasattr(collection, "doi") or hasattr(collection, "draftdoi"):
        context["error"] = "This collection already has a DOI."
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
        Collection.objects.select_related("cached_counts", "creator"), pk=pk
    )

    # TODO: if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.select_related("accession").order_by("created").distinct(),
    )

    paginator = CursorPagination(ordering=("created",))
    cursor_input = CursorPagination.Input(
        limit=request.GET.get("limit", 30), cursor=request.GET.get("cursor")
    )

    # prevent the paginator from doing a slow count.
    if hasattr(collection, "cached_counts"):
        images = qs_with_hardcoded_count(images, ("created",), collection.cached_counts.image_count)

    page = paginator.paginate_queryset(images, pagination=cursor_input, request=request)

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
