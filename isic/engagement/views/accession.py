from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls.base import reverse

from isic.ingest.forms import PublishForm
from isic.ingest.models import Accession
from isic.ingest.services.publish import initialize_publish
from isic.ingest.views.review import render_review_gallery


@staff_member_required
def engagement_accession_list(request):
    only_in_flight = request.GET.get("only_in_flight", "1") == "1"

    accessions = (
        Accession.objects.from_engagement_platform()
        .select_related("engagement", "cohort__contributor", "creator", "image", "review")
        .order_by("-created")
    )
    num_publishable = accessions.publishable().count()

    if only_in_flight:
        accessions = accessions.in_flight()

    paginator = Paginator(accessions, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "engagement/accession_list.html",
        {"page": page, "only_in_flight": only_in_flight, "num_publishable": num_publishable},
    )


@staff_member_required
def engagement_accession_review(request):
    return render_review_gallery(
        request,
        accessions=Accession.objects.from_engagement_platform(),
        context={
            "breadcrumbs": [
                [reverse("engagement/accession-list"), "Engagement Accessions"],
                ["#", "Review"],
            ]
        },
    )


@staff_member_required
def engagement_accession_publish(request):
    accessions = Accession.objects.from_engagement_platform()
    form = PublishForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        publish_requests = initialize_publish(
            accessions=accessions,
            publisher=request.user,
            # the engagement platform has no separate unembargo step, so publishing an accession
            # from it publishes and unembargoes in one move.
            public=True,
            collections=form.cleaned_data["additional_collections"],
        )
        num_publishing = sum(
            publish_request.accessions.count() for publish_request in publish_requests
        )

        messages.success(
            request,
            f"Publishing {intcomma(num_publishing)} images. This may take several minutes.",
        )
        return HttpResponseRedirect(reverse("engagement/accession-list"))

    # attribution and the destination collection both come from the cohort, and the engagement
    # platform's accessions span cohorts, so the confirmation has to break the count down.
    cohorts = list(
        accessions.publishable()
        .values(
            "cohort_id",
            "cohort__name",
            "cohort__default_attribution",
            "cohort__default_copyright_license",
            "cohort__contributor__institution_name",
        )
        .annotate(num_publishable=Count("pk"))
        .order_by("cohort__name")
    )

    return render(
        request,
        "engagement/accession_publish.html",
        {
            "form": form,
            "cohorts": cohorts,
            "num_publishable": sum(cohort["num_publishable"] for cohort in cohorts),
            "breadcrumbs": [
                [reverse("engagement/accession-list"), "Engagement Accessions"],
                ["#", "Publish"],
            ],
        },
    )
