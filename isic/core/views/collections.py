from collections.abc import Iterable
import csv
from datetime import UTC, datetime
from typing import TypedDict

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
from django_stubs_ext import StrOrPromise

from isic.core.filters import CollectionFilter
from isic.core.forms.collection import CollectionForm
from isic.core.models import Collection
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.services import image_metadata_csv
from isic.core.services.collection import collection_create, collection_update
from isic.core.services.collection.doi import (
    collection_build_doi_preview,
    collection_check_create_doi_allowed,
    collection_create_doi,
)
from isic.ingest.models import Contributor


def collection_list(request):
    # TODO: should the image count be access controlled too?
    collections = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.order_by("-pinned", "name"),
    )

    if request.user.is_authenticated:
        counts = collections.aggregate(
            pinned=Count("pk", filter=Q(pinned=True)),
            shared_with_me=Count("pk", filter=Q(shares=request.user)),
            mine=Count("pk", filter=Q(creator=request.user)),
            all_=Count("pk"),
        )
    else:
        counts = collections.aggregate(
            pinned=Count("pk", filter=Q(pinned=True)),
            all_=Count("pk"),
        )

    filter_ = CollectionFilter(request.GET, queryset=collections, user=request.user)
    paginator = Paginator(filter_.qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    collection_counts = (
        Collection.images.through.objects.filter(
            collection_id__in=page.object_list.values_list("pk", flat=True)  # type: ignore[attr-defined]
        )
        .values("collection_id")
        .annotate(num_images=Count("image_id"))
    )

    collection_counts = {c["collection_id"]: c["num_images"] for c in collection_counts}

    for collection in page:
        collection.num_images = collection_counts.get(collection.pk, 0)

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
    # StreamingHttpResponse requires a File-like class that has a 'write' method
    class Buffer:
        def write(self, value: str) -> bytes:
            return value.encode("utf-8")

    collection = get_object_or_404(Collection, pk=pk)
    qs = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.all(),
    )

    def csv_rows(buffer: Buffer) -> Iterable[bytes]:
        collection_metadata = image_metadata_csv(qs=qs)
        writer = csv.DictWriter(buffer, next(collection_metadata))
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
    Context = TypedDict(  # noqa: UP013
        "Context", {"collection": Collection, "error": StrOrPromise | None, "preview": dict | None}
    )
    context: Context = {"collection": collection, "error": None, "preview": None}

    if request.method == "POST":
        try:
            collection_create_doi(user=request.user, collection=collection)
            return HttpResponseRedirect(reverse("core/collection-detail", args=[collection.pk]))
        except ValidationError as e:
            context["error"] = e.message
    else:
        try:
            collection_check_create_doi_allowed(user=request.user, collection=collection)
        except ValidationError as e:
            context["error"] = e.message
        else:
            context["preview"] = collection_build_doi_preview(collection=collection)

    return render(
        request,
        "core/collection_create_doi.html",
        context,
    )


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
def collection_detail(request, pk):
    collection = get_object_or_404(Collection, pk=pk)

    # TODO: if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.select_related("accession").order_by("created").distinct(),
    )

    paginator = Paginator(images, 30)
    page = paginator.get_page(request.GET.get("page"))
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
            "images": page,
            "num_images": paginator.count,
            "image_removal_mode": image_removal_mode,
            "show_shares": (request.user.is_staff or request.user == collection.creator)
            and not collection.public,
        },
    )
