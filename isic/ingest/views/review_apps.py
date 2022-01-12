from collections import defaultdict

from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from isic.core.permissions import needs_object_permission
from isic.ingest.models import Accession, Cohort, DistinctnessMeasure

from . import make_breadcrumbs


@method_decorator(staff_member_required, name='dispatch')
class ReviewAppView(ListView):
    title = ''

    paginate_by = 50
    template_name = 'ingest/review_app.html'

    def get_unreviewed_filter(self):
        raise NotImplementedError

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        filters = Q(cohort=self.cohort)
        unreviewed = self.get_unreviewed_filter()
        return Accession.objects.filter(filters & unreviewed).order_by(
            'metadata__diagnosis', 'created'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                'title': self.title,
                'cohort': self.cohort,
                'buttons': self.buttons,
                'checks': self.checks,
                'breadcrumbs': make_breadcrumbs(self.cohort) + [['#', self.title]],
            }
        )
        return context


class GroupedReviewAppView(ReviewAppView):
    paginate_by = 10

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grouped_review_app'] = True
        return context


class DiagnosisReviewAppView(ReviewAppView):
    title = 'Diagnosis Review'
    buttons = {'reject': {'diagnosis_check': 'Reject Diagnosis'}}
    checks = ['diagnosis_check']

    def get_unreviewed_filter(self):
        return Q(diagnosis_check__isnull=True)


class QualityPhiReviewAppView(ReviewAppView):
    title = 'Quality & PHI Review'
    buttons = {
        'reject': {
            'quality_check': 'Reject Quality',
            'phi_check': 'Reject PHI',
        }
    }
    checks = ['quality_check', 'phi_check']

    def get_unreviewed_filter(self):
        return Q(quality_check__isnull=True) & Q(phi_check__isnull=True)


class DuplicateReviewAppView(GroupedReviewAppView):
    title = 'Duplicate Review'
    buttons = {'reject': {'duplicate_check': 'Reject Duplicate'}}
    checks = ['duplicate_check']

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        return (
            DistinctnessMeasure.objects.filter(
                checksum__in=DistinctnessMeasure.objects.values('checksum')
                .annotate(is_duplicate=Count('checksum'))
                .annotate(
                    num_unreviewed_accessions=Count(
                        'accession', filter=Q(accession__duplicate_check=None)
                    )
                )
                .filter(
                    accession__cohort=self.cohort,
                    is_duplicate__gt=1,
                    num_unreviewed_accessions__gt=0,
                )
                .values_list('checksum', flat=True),
            )
            .order_by('checksum')
            .distinct('checksum')
            .values_list('checksum', flat=True)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouped_accessions: dict[str, list] = defaultdict(list)
        relevant_accessions = Accession.objects.select_related('distinctnessmeasure').filter(
            cohort=self.cohort,
            distinctnessmeasure__checksum__in=self.get_queryset(),
        )
        for accession in relevant_accessions:
            grouped_accessions[accession.distinctnessmeasure.checksum].append(accession)
            context.update(
                {
                    'buttons': self.buttons,
                    'cohort': self.cohort,
                    'grouped_accessions': grouped_accessions,
                }
            )
        return context


@staff_member_required
@needs_object_permission('ingest.view_cohort', (Cohort, 'pk', 'cohort_pk'))
def lesion_review(request, cohort_pk):
    cohort = get_object_or_404(Cohort, pk=cohort_pk)
    lesions_with_unreviewed_accessions = (
        cohort.accessions.values('metadata__lesion_id')
        .annotate(num_unreviewed_accessions=Count(1, filter=Q(lesion_check=None)))
        .filter(num_unreviewed_accessions__gt=0)
        .values_list('metadata__lesion_id', flat=True)
        .distinct()
        .order_by('metadata__lesion_id')
    )
    paginator = Paginator(lesions_with_unreviewed_accessions, 10)
    page = paginator.get_page(request.GET.get('page'))

    grouped_accessions: dict[str, list] = defaultdict(list)
    relevant_accessions = cohort.accessions.filter(metadata__lesion_id__in=page).order_by(
        'metadata__acquisition_day'
    )
    for accession in relevant_accessions:
        grouped_accessions[accession.metadata['lesion_id']].append(accession)

    return render(
        request,
        'ingest/review_app.html',
        {
            'title': 'Lesion Review',
            'buttons': {
                'reject': {'lesion_check': 'Reject Lesion'},
            },
            'checks': ['lesion_check'],
            'breadcrumbs': make_breadcrumbs(cohort) + [['#', 'Lesion Review']],
            'grouped_review_app': True,
            'cohort': cohort,
            'page_obj': page,
            'grouped_accessions': grouped_accessions,
        },
    )
