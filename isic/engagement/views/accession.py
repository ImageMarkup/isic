from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls.base import reverse

from isic.ingest.models import Accession
from isic.ingest.views.review import render_review_gallery


@staff_member_required
def engagement_accession_list(request):
    only_in_flight = request.GET.get("only_in_flight", "1") == "1"

    accessions = (
        Accession.objects.from_engagement_platform()
        .select_related("engagement", "cohort__contributor", "creator", "image", "review")
        .order_by("-created")
    )

    if only_in_flight:
        accessions = accessions.in_flight()

    paginator = Paginator(accessions, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "engagement/accession_list.html",
        {"page": page, "only_in_flight": only_in_flight},
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
