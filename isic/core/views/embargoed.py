from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import BooleanField, Case, Count, F, Max, Min, When
from django.shortcuts import render

from isic.core.models.image import Image
from isic.ingest.models.cohort import Cohort


@staff_member_required
def embargoed_dashboard(request):
    cohorts_with_embargoed = (
        Cohort.objects.filter(accessions__image__public=False)
        .annotate(
            embargoed_count=Count("accessions__image"),
            oldest_embargoed=Min("accessions__created"),
            newest_embargoed=Max("accessions__created"),
            # define images being uploaded within the same 1 week period as a single time point
            multiple_time_points=Case(
                When(newest_embargoed__gt=F("oldest_embargoed") + timedelta(weeks=1), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        )
        .select_related("contributor")
        .order_by("oldest_embargoed")
    )

    total_embargoed = Image.objects.filter(public=False).count()

    context = {
        "cohorts_with_embargoed": cohorts_with_embargoed,
        "total_embargoed": total_embargoed,
    }

    return render(request, "core/embargoed_dashboard.html", context)
