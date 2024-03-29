from collections.abc import Iterable
import csv
from datetime import UTC, datetime
import json

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.http import HttpRequest, HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, render

from isic.core.forms.search import ImageSearchForm
from isic.core.models import Collection, Image
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.services import staff_image_metadata_csv
from isic.studies.models import Study


@needs_object_permission("core.view_image", (Image, "pk", "pk"))
def image_detail(request, pk):
    image = get_object_or_404(
        Image.objects.select_related(
            "accession__cohort__contributor__creator", "accession__review"
        ),
        pk=pk,
    )

    studies = get_visible_objects(
        request.user,
        "studies.view_study",
        Study.objects.select_related("creator"),
    )
    studies = (
        studies.filter(tasks__image=image)
        .annotate(
            num_responses=Count(
                "tasks__annotation__responses",
                filter=Q(tasks__image=image),
                distinct=True,
            )
        )
        .annotate(
            num_markups=Count(
                "tasks__annotation__markups",
                filter=Q(tasks__image=image),
                distinct=True,
            )
        )
        .distinct()
    )

    ctx = {
        "image": image,
        "pinned_collections": get_visible_objects(
            request.user,
            "core.view_collection",
            image.collections.filter(pinned=True).order_by("name"),
        ),
        "other_patient_images": get_visible_objects(
            request.user,
            "core.view_image",
            image.same_patient_images().select_related("accession"),
        ),
        "other_lesion_images": get_visible_objects(
            request.user,
            "core.view_image",
            image.same_lesion_images().select_related("accession"),
        ),
        "studies": studies,
    }

    ctx["metadata"] = dict(sorted(image.metadata.items()))
    if request.user.has_perm("core.view_full_metadata", image):
        ctx["unstructured_metadata"] = dict(
            sorted(image.accession.unstructured_metadata.value.items())
        )
        ctx["metadata_versions"] = image.accession.metadata_versions.select_related(
            "creator"
        ).differences()

    ctx["sections"] = {
        "metadata": "Metadata",
        "studies": f"Studies ({studies.count()})",
    }

    if request.user.is_staff:
        ctx["sections"]["patient_images"] = (
            f'Other Patient Images ({ctx["other_patient_images"].count()})'
        )
        ctx["sections"]["lesion_images"] = (
            f'Other Lesion Images ({ctx["other_lesion_images"].count()})'
        )
        ctx["sections"]["ingestion_details"] = "Ingestion Details"

    return render(request, "core/image_detail/base.html", ctx)


def image_browser(request):
    collections = get_visible_objects(
        request.user, "core.view_collection", Collection.objects.order_by("name")
    )
    search_form = ImageSearchForm(
        request.GET,
        user=request.user,
        collections=collections,
    )
    qs: QuerySet[Image] = Image.objects.none()
    if search_form.is_valid():
        qs = search_form.results

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page"))

    if request.user.is_authenticated:
        addable_collections = collections.filter(locked=False)

        if not request.user.is_staff:
            addable_collections = addable_collections.filter(creator=request.user)
    else:
        addable_collections = []

    return render(
        request,
        "core/image_browser.html",
        {
            "total_images": page.paginator.count,
            "images": page,
            # The user can only add images to collections that are theirs and unlocked.
            "collections": addable_collections,
            # This gets POSTed to the populate endpoint if called
            "search_body": json.dumps(request.GET),
            "form": search_form,
        },
    )


@staff_member_required
def image_list_export(request: HttpRequest) -> HttpResponse:
    return render(request, "core/image_list_export.html")


@staff_member_required
def image_list_metadata_download(request: HttpRequest):
    # StreamingHttpResponse requires a File-like class that has a 'write' method
    class Buffer:
        def write(self, value: str) -> bytes:
            return value.encode("utf-8")

    def csv_rows(buffer: Buffer) -> Iterable[bytes]:
        # use repeatable read for the headers and rows to make sure they match
        with transaction.atomic():
            cursor = connection.cursor()
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

            qs = Image.objects.all()
            image_csv = staff_image_metadata_csv(qs=qs)
            writer = csv.DictWriter(buffer, next(image_csv))
            yield writer.writeheader()

            for metadata_row in image_csv:
                yield writer.writerow(metadata_row)

    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    response = StreamingHttpResponse(csv_rows(Buffer()), content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="isic_accession_metadata_{current_time}.csv"'
    )

    return response
