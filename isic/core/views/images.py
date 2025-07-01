import json

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from isic.core.forms.search import ImageSearchForm
from isic.core.models import Collection, Image
from isic.core.pagination import CursorPagination, qs_with_hardcoded_count
from isic.core.permissions import get_visible_objects, needs_object_permission
from isic.core.search import get_elasticsearch_client
from isic.core.tasks import generate_staff_image_list_metadata_csv
from isic.studies.models import Study
from isic.types import AuthenticatedHttpRequest

# Show this many related images e.g. other patient images, other lesion images.
# Lesions are typically <= 20 images, but patients can be hundreds.
MAX_RELATED_SHOW_FIRST_N = 50


def resolve_image_identifier(view_func):
    from django.http import HttpResponsePermanentRedirect
    from django.urls import reverse

    def wrapper(request, image_identifier):
        if image_identifier.startswith("ISIC_"):
            return view_func(request, isic_id=image_identifier)

        filter_ = (
            Q(pk=image_identifier)
            if image_identifier.isdigit()
            else Q(accession__girder_id=image_identifier)
        )

        image = Image.objects.filter(filter_).order_by().first()
        if image:
            redirect_url = reverse("core/image-detail", kwargs={"image_identifier": image.isic_id})
            return HttpResponsePermanentRedirect(redirect_url)

        return view_func(request, isic_id=image_identifier)

    return wrapper


@resolve_image_identifier
@needs_object_permission("core.view_image", (Image, "isic_id", "isic_id"))
def image_detail(request, isic_id):
    image = get_object_or_404(
        Image.objects.select_related(
            "accession__cohort__contributor__creator", "accession__review__creator"
        ),
        isic_id=isic_id,
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

    other_patient_images = get_visible_objects(
        request.user,
        "core.view_image",
        image.same_patient_images().select_related("accession"),
    )

    other_lesion_images = get_visible_objects(
        request.user,
        "core.view_image",
        image.same_lesion_images().select_related("accession"),
    )

    ctx = {
        "image": image,
        "pinned_collections": get_visible_objects(
            request.user,
            "core.view_collection",
            image.collections.filter(pinned=True).order_by("name"),
        ),
        "other_patient_images": other_patient_images,
        "other_patient_images_count": other_patient_images.count(),
        "other_lesion_images": other_lesion_images,
        "other_lesion_images_count": other_lesion_images.count(),
        "MAX_RELATED_SHOW_FIRST_N": MAX_RELATED_SHOW_FIRST_N,
        "studies": studies,
        "unstructured_metadata": {},
        "metadata_versions": [],
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
            f"Other Patient Images ({ctx['other_patient_images_count']})"
        )
        ctx["sections"]["lesion_images"] = (
            f"Other Lesion Images ({ctx['other_lesion_images_count']})"
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

        if settings.ISIC_USE_ELASTICSEARCH_COUNTS:
            es_query = search_form.serializer.to_es_query(request.user)
            es_count = get_elasticsearch_client().count(
                index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
                body={"query": es_query},
            )["count"]
            qs = qs_with_hardcoded_count(qs, ("created",), es_count)

    paginator = CursorPagination(ordering=("created",))
    cursor_input = CursorPagination.Input(
        limit=request.GET.get("limit", 30), cursor=request.GET.get("cursor")
    )

    page = paginator.paginate_queryset(qs, pagination=cursor_input, request=request)

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
            "total_images": qs.count(),
            "images": page["results"],
            "page": page,
            # The user can only add images to collections that are theirs and unlocked.
            "collections": addable_collections,
            # This gets POSTed to the populate endpoint if called
            "search_body": json.dumps(request.GET),
            "form": search_form,
        },
    )


@staff_member_required
def staff_image_list_export(request: AuthenticatedHttpRequest) -> HttpResponse:
    return render(request, "core/image_list_export.html")


@staff_member_required
def staff_image_list_metadata_download(request: AuthenticatedHttpRequest):
    generate_staff_image_list_metadata_csv.delay_on_commit(request.user.id)

    messages.add_message(
        request,
        messages.INFO,
        f"Preparing the CSV, a download link will be sent to {request.user.email} when complete.",
    )

    return HttpResponseRedirect(reverse("core/image-list-export"))
