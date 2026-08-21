from collections import defaultdict
import math

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.db.models.query_utils import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from isic.core.permissions import needs_object_permission
from isic.ingest.models import Cohort
from isic.ingest.models.accession import Accession, AccessionQuerySet, AccessionStatus

from . import make_breadcrumbs

REVIEW_PER_PAGE = 500


def _review_progress(accessions: AccessionQuerySet) -> dict:
    ingested_and_publishable = Q(image__isnull=True, status=AccessionStatus.SUCCEEDED)
    counts = accessions.aggregate(
        reviewed=Count("id", filter=ingested_and_publishable & ~Q(review=None)),
        reviewable=Count("id", filter=ingested_and_publishable),
    )

    return {
        "num_reviewed": counts["reviewed"],
        "num_reviewable": counts["reviewable"],
        "num_unreviewed": counts["reviewable"] - counts["reviewed"],
        "percentage": (
            0
            if counts["reviewable"] == 0
            else math.floor(counts["reviewed"] / counts["reviewable"] * 100)
        ),
    }


def render_review_gallery(
    request: HttpRequest, *, accessions: AccessionQuerySet, context: dict
) -> HttpResponse:
    """
    Render the review gallery over an arbitrary set of accessions.

    The gallery only needs a queryset, so the same interface serves a single cohort and the
    cross cohort sets other apps assemble, like the engagement platform's uploads.
    """
    paginator = Paginator(
        accessions.select_related("unstructured_metadata")
        .unreviewed()
        .order_by("original_blob_name"),
        REVIEW_PER_PAGE,
    )
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "ingest/review_gallery.html",
        {
            "progress": _review_progress(accessions),
            "page_obj": page,
            **context,
        },
    )


def _render_review_grouped_by_lesion(
    request: HttpRequest, accessions: AccessionQuerySet, context: dict
) -> HttpResponse:
    lesions_with_unreviewed_accessions = (
        accessions.unreviewed()
        .values("lesion_id")
        .alias(num_unreviewed_accessions=Count(1, filter=Q(review=None)))
        .filter(num_unreviewed_accessions__gt=0)
        .values_list("lesion_id", flat=True)
        .distinct()
        .order_by("lesion_id")
    )
    paginator = Paginator(lesions_with_unreviewed_accessions, 50)
    page = paginator.get_page(request.GET.get("page"))

    grouped_accessions: dict[str, list] = defaultdict(list)
    relevant_accessions = (
        # show accessions even if they've been reviewed or published, because there are *unreviewed*
        # accessions with this lesion id still. displaying the entire context is necessary.
        accessions.select_related("unstructured_metadata")
        .ingested()
        .select_related("review")
        .filter(lesion_id__in=page)
        .order_by("acquisition_day")
    )
    for accession in relevant_accessions:
        grouped_accessions[accession.lesion_id].append(accession)

    return render(
        request,
        "ingest/review_lesion_gallery.html",
        {
            "progress": _review_progress(accessions),
            "page_obj": page,
            "grouped_accessions": dict(grouped_accessions),
            **context,
        },
    )


@staff_member_required
def ingest_review(request):
    cohorts = Cohort.objects.select_related("contributor", "creator")

    hide_empty = request.GET.get("hide_empty", "true").lower() == "true"

    if hide_empty:
        # only include cohorts with non-skipped accessions
        cohorts = cohorts.annotate(
            has_non_skipped_accessions=Exists(
                Accession.objects.filter(cohort=OuterRef("pk")).exclude(
                    status=AccessionStatus.SKIPPED
                )
            )
        ).filter(has_non_skipped_accessions=True)

    cohorts = cohorts.order_by("-created")
    paginator = Paginator(cohorts, 10)
    cohorts_page = paginator.get_page(request.GET.get("page"))
    unreviewed_counts = (
        Accession.objects.filter(
            cohort__in=cohorts_page, status=AccessionStatus.SUCCEEDED, review=None
        )
        .values("cohort_id")
        .annotate(unreviewed_count=Count("id"))
    )
    unreviewed_counts = {row["cohort_id"]: row["unreviewed_count"] for row in unreviewed_counts}

    for cohort in cohorts_page:
        cohort.unreviewed_count = unreviewed_counts.get(cohort.pk, 0)

    return render(
        request,
        "ingest/ingest_review.html",
        {
            "cohorts": cohorts_page,
            "num_cohorts": paginator.count,
            "paginator": paginator,
            "hide_empty": hide_empty,
        },
    )


@staff_member_required
@needs_object_permission("ingest.view_cohort", (Cohort, "pk", "cohort_pk"))
def cohort_review(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    accessions = cohort.accessions.all()
    context = {"breadcrumbs": [*make_breadcrumbs(cohort), ["#", "Review"]]}

    if request.GET.get("grouped_by_lesion"):
        return _render_review_grouped_by_lesion(request, accessions, context)

    return render_review_gallery(request, accessions=accessions, context=context)
