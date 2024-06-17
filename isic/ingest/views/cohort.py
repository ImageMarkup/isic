from collections import defaultdict
import itertools

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls.base import reverse

from isic.core.permissions import needs_object_permission
from isic.ingest.forms import MergeCohortForm, PublishCohortForm
from isic.ingest.models import Cohort
from isic.ingest.models.accession import Accession, AccessionStatus
from isic.ingest.models.contributor import Contributor
from isic.ingest.services.cohort import cohort_merge, cohort_publish_initialize
from isic.ingest.views import make_breadcrumbs


def cohort_counts(cohort: Cohort) -> dict[str, int]:
    reviewable = Q(image__isnull=True, status=AccessionStatus.SUCCEEDED)
    return cohort.accessions.aggregate(
        accession_count=Count("pk"),
        patient_count=Count("patient", distinct=True),
        lesion_count=Count("lesion", distinct=True),
        published_count=Count("pk", filter=Q(image__isnull=False)),
        unreviewed_count=Count("pk", filter=reviewable & Q(review=None)),
        accepted_count=Count("pk", filter=reviewable & Q(review__value=True)),
        rejected_count=Count("pk", filter=reviewable & Q(review__value=False)),
    )


@staff_member_required
def cohort_list(request):
    contributors = Contributor.objects.prefetch_related(
        # the cohorts call needs to be ordered by attribution/name for the below itertools.groupby
        # call to work correctly.
        Prefetch("cohorts", queryset=Cohort.objects.order_by("attribution", "name"))
    ).order_by("institution_name")

    counts_by_cohort = Accession.objects.values("cohort_id").annotate(
        lesion_count=Count("lesion", distinct=True),
        patient_count=Count("patient", distinct=True),
        accession_count=Count("pk"),
    )
    counts_by_cohort = {row["cohort_id"]: row for row in counts_by_cohort}

    rows = []
    for contributor in contributors.all():
        display_contributor = True
        for attribution, cohorts in itertools.groupby(
            contributor.cohorts.all(),
            key=lambda cohort: cohort.attribution,
        ):
            display_attribution = True
            for cohort in cohorts:
                aggregate_data = counts_by_cohort.get(cohort.pk, defaultdict(int))
                rows.append(
                    {
                        "contributor": contributor,
                        "display_contributor": display_contributor,
                        "attribution": attribution,
                        "display_attribution": display_attribution,
                        "cohort": cohort,
                        "accession_count": aggregate_data["accession_count"],
                        "lesion_count": aggregate_data["lesion_count"],
                        "patient_count": aggregate_data["patient_count"],
                    }
                )
                display_contributor = display_attribution = False

    return render(
        request,
        "ingest/cohort_list.html",
        {"rows": rows},
    )


@staff_member_required
def cohort_detail(request, pk):
    cohort = get_object_or_404(Cohort.objects.select_related("creator"), pk=pk)
    paginator = Paginator(cohort.accessions.select_related("unstructured_metadata").ingested(), 50)
    accessions = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "ingest/cohort_detail.html",
        {
            "cohort": cohort,
            "counts": cohort_counts(cohort),
            "accessions": accessions,
            "breadcrumbs": make_breadcrumbs(cohort),
        },
    )


@staff_member_required
def merge_cohorts(request):
    form = MergeCohortForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cohort = form.cleaned_data["cohort"]
        cohort_to_merge = form.cleaned_data["cohort_to_merge"]
        try:
            cohort_merge(dest_cohort=cohort, src_cohort=cohort_to_merge)
        except ValidationError as e:
            form.add_error(None, e)
        else:
            messages.success(request, "Cohort merged successfully.")
            return HttpResponseRedirect(reverse("cohort-detail", args=[cohort.pk]))

    return render(
        request,
        "ingest/merge_cohorts.html",
        {"form": form},
    )


@staff_member_required  # TODO: who gets to publish a cohort? anyone who can view it?
@needs_object_permission("ingest.view_cohort", (Cohort, "pk", "pk"))
def publish_cohort(request, pk):
    cohort = get_object_or_404(Cohort, pk=pk)

    form = PublishCohortForm(request.POST)

    if request.method == "POST" and form.is_valid():
        cohort_publish_initialize(
            cohort=cohort,
            publisher=request.user,
            public=form.cleaned_data["public"],
            collection_ids=list(
                form.cleaned_data["additional_collections"].values_list("id", flat=True)
            ),
        )

        # define the count before publishing so it's accurate in development when
        # accessions are published synchronously.
        publishable_accession_count = cohort.accessions.publishable().count()

        messages.add_message(
            request,
            messages.SUCCESS,
            f"Publishing {intcomma(publishable_accession_count)} images. This may take several minutes.",  # noqa: E501
        )
        return HttpResponseRedirect(reverse("cohort-detail", args=[cohort.pk]))

    ctx = {
        "form": form,
        "cohort": cohort,
        "breadcrumbs": [*make_breadcrumbs(cohort), ["#", "Publish Cohort"]],
        "num_accessions": cohort.accessions.count(),
        "num_publishable": cohort.accessions.publishable().count(),
    }
    ctx["num_unpublishable"] = ctx["num_accessions"] - ctx["num_publishable"]

    return render(request, "ingest/cohort_publish.html", ctx)
