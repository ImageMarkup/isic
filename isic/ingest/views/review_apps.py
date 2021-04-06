from collections import defaultdict

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from isic.ingest.models import Accession, Cohort, DistinctnessMeasure
from isic.ingest.util import make_breadcrumbs


@method_decorator(staff_member_required, name='dispatch')
class ReviewAppView(ListView):
    title = ''

    paginate_by = 50
    template_name = 'ingest/review_app.html'

    def get_unreviewed_filter(self):
        raise NotImplementedError

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        filters = Q(upload__cohort=self.cohort)
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

    def get_unreviewed_filter(self):
        """
        Filter out the unreviewed duplicates.

        This is a little tricky because we only want to filter the GROUP (aka checksum) if
        any accessions in the group are still unreviewed (for duplicates).
        """
        checksums_with_any_unreviewed_accessions = (
            DistinctnessMeasure.objects.values('checksum')
            .annotate(
                num_unreviewed_accessions=Count(
                    'accession', filter=Q(accession__duplicate_check=None)
                )
            )
            .filter(num_unreviewed_accessions__gt=0)
            .values('checksum')
        )
        return Q(checksum__in=checksums_with_any_unreviewed_accessions)

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        return (
            DistinctnessMeasure.objects.filter(
                accession__upload__cohort=self.cohort,
                checksum__in=DistinctnessMeasure.objects.values('checksum')
                .annotate(is_duplicate=Count('checksum'))
                .filter(accession__upload__cohort=self.cohort, is_duplicate__gt=1)
                .filter(self.get_unreviewed_filter())
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
            upload__cohort=self.cohort,
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


class LesionReviewAppView(GroupedReviewAppView):
    title = 'Lesion Review'
    buttons = {
        'reject': {'lesion_check': 'Reject Lesion'},
    }
    checks = ['lesion_check']

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        return (
            Accession.objects.filter(upload__cohort=self.cohort, metadata__lesion_id__isnull=False)
            .order_by('metadata__lesion_id', 'metadata__acquisition_day')
            .distinct('metadata__lesion_id')
            .values_list('metadata__lesion_id', flat=True)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grouped_accessions: dict[str, list] = defaultdict(list)
        relevant_accessions = Accession.objects.filter(
            upload__cohort=self.cohort, metadata__lesion_id__in=self.get_queryset()
        )
        for accession in relevant_accessions:
            grouped_accessions[accession.metadata['lesion_id']].append(accession)

        context.update(
            {
                'cohort': self.cohort,
                'grouped_accessions': grouped_accessions,
            }
        )
        return context
