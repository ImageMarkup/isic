from collections import defaultdict
import math

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404, render

from isic.core.permissions import needs_object_permission
from isic.ingest.models import Cohort

from . import make_breadcrumbs


def _cohort_review_progress(cohort: Cohort) -> dict:
    num_reviewed = cohort.accessions.reviewed().count()
    num_reviewable = cohort.accessions.reviewable().count()

    return {
        'num_reviewed': num_reviewed,
        'num_reviewable': num_reviewable,
        'percentage': 0 if num_reviewable == 0 else math.floor(num_reviewed / num_reviewable * 100),
    }


@staff_member_required
def ingest_review(request):
    cohorts = Cohort.objects.select_related('contributor', 'creator').order_by('-created')
    paginator = Paginator(cohorts, 10)
    cohorts_page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/ingest_review.html',
        {'cohorts': cohorts_page, 'num_cohorts': paginator.count, 'paginator': paginator},
    )


@staff_member_required
@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def cohort_review(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)

    if request.GET.get('grouped_by_lesion'):
        return _cohort_review_grouped_by_lesion(request, cohort)

    paginator = Paginator(cohort.accessions.unreviewed(), 100)
    page = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'ingest/review_gallery.html',
        {
            'progress': _cohort_review_progress(cohort),
            'cohort': cohort,
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Review']],
            'page_obj': page,
        },
    )


def _cohort_review_grouped_by_lesion(request, cohort: Cohort):
    lesions_with_unreviewed_accessions = (
        cohort.accessions.unreviewed()
        .values('metadata__lesion_id')
        .alias(num_unreviewed_accessions=Count(1, filter=Q(review=None)))
        .filter(num_unreviewed_accessions__gt=0)
        .values_list('metadata__lesion_id', flat=True)
        .distinct()
        .order_by('metadata__lesion_id')
    )
    paginator = Paginator(lesions_with_unreviewed_accessions, 50)
    page = paginator.get_page(request.GET.get('page'))

    grouped_accessions: dict[str, list] = defaultdict(list)
    relevant_accessions = (
        # show accessions even if they've been reviewed or published, because there are *unreviewed*
        # accessions with this lesion id still. displaying the entire context is necessary.
        cohort.accessions.ingested()
        .select_related('review')
        .filter(metadata__lesion_id__in=page)
        .order_by('metadata__acquisition_day')
    )
    for accession in relevant_accessions:
        grouped_accessions[accession.metadata['lesion_id']].append(accession)

    return render(
        request,
        'ingest/review_lesion_gallery.html',
        {
            'progress': _cohort_review_progress(cohort),
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Review']],
            'cohort': cohort,
            'page_obj': page,
            'grouped_accessions': dict(grouped_accessions),
        },
    )
