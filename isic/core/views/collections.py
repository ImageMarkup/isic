import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query_utils import Q
from django.http import HttpResponse
from django.http.response import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.defaultfilters import slugify
from django.urls.base import reverse

from isic.core.filters import CollectionFilter
from isic.core.forms.collection import CollectionForm
from isic.core.models import Collection
from isic.core.models.base import CopyrightLicense
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.services import _image_metadata_csv_headers, image_metadata_csv_rows
from isic.core.services.collection import collection_create, collection_update
from isic.core.services.collection.doi import collection_build_doi_preview, collection_create_doi
from isic.ingest.models import Contributor
from isic.ingest.models.accession import Accession


def collection_list(request):
    # TODO: should the image count be access controlled too?
    collections = get_visible_objects(
        request.user,
        "core.view_collection",
        Collection.objects.annotate(num_images=Count("images", distinct=True)).order_by(
            "-pinned", "name"
        ),
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

    filter = CollectionFilter(request.GET, queryset=collections, user=request.user)
    paginator = Paginator(filter.qs, 25)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/collection_list.html",
        {"collections": page, "filter": filter, "counts": counts},
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
        request, "core/collection_create_or_edit.html", {"form": form, "collection": collection}
    )


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
def collection_download_metadata(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    qs = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.all(),
    )
    current_time = datetime.utcnow().strftime("%Y-%m-%d")
    response = HttpResponse(content_type="text/csv")
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{slugify(collection.name)}_metadata_{current_time}.csv"'

    writer = csv.DictWriter(response, _image_metadata_csv_headers(qs=qs))
    writer.writeheader()

    for metadata_row in image_metadata_csv_rows(qs=qs):
        writer.writerow(metadata_row)

    return response


@needs_object_permission("core.view_collection", (Collection, "pk", "pk"))
@needs_object_permission("core.create_doi", (Collection, "pk", "pk"))
def collection_create_doi_(request, pk):
    collection = get_object_or_404(Collection, pk=pk)
    context = {"collection": collection}

    if request.method == "POST":
        try:
            collection_create_doi(user=request.user, collection=collection)
            return HttpResponseRedirect(reverse("core/collection-detail", args=[collection.pk]))
        except ValidationError:
            pass
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

    # TODO; if they can see the collection they can see the images?
    images = get_visible_objects(
        request.user,
        "core.view_image",
        collection.images.select_related("accession").order_by("created").distinct(),
    )
    license_counts = (
        Accession.objects.filter(image__in=images)
        .values("copyright_license")
        .aggregate(
            **{
                license: Count("copyright_license", filter=Q(copyright_license=license))
                for license in CopyrightLicense.values
            }
        )
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
            "license_counts": license_counts,
            "num_images": paginator.count,
            "image_removal_mode": image_removal_mode,
        },
    )
