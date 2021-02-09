from collections import defaultdict

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count
from django.db.models.query_utils import Q
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from isic.ingest.models import Accession, Cohort, DistinctnessMeasure


@method_decorator(staff_member_required, name='dispatch')
class ReviewAppView(ListView):
    title = ''

    paginate_by = 25
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
        context.update({'title': self.title, 'cohort': self.cohort, 'buttons': self.buttons})
        return context


class GroupedReviewAppView(ReviewAppView):
    paginate_by = 10
    template_name = 'ingest/grouped_review_app.html'


class DiagnosisReviewAppView(ReviewAppView):
    title = 'Diagnosis Review'
    buttons = {'reject': {'diagnosis_check': 'Reject Diagnosis'}}

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

    def get_unreviewed_filter(self):
        return Q(quality_check__isnull=True) | Q(phi_check__isnull=True)


class DuplicateReviewAppView(GroupedReviewAppView):
    title = 'Duplicate Review'
    buttons = {'reject': {'duplicate_check': 'Reject Duplicate'}}

    def get_queryset(self):
        self.cohort = get_object_or_404(Cohort, pk=self.kwargs['cohort_pk'])
        return (
            DistinctnessMeasure.objects.filter(
                accession__upload__cohort=self.cohort,
                checksum__in=DistinctnessMeasure.objects.values('checksum')
                .annotate(is_duplicate=Count('checksum'))
                .filter(accession__upload__cohort=self.cohort, is_duplicate__gt=1)
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
        'accept': {'lesion_check': 'Accept Lesion'},
    }

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
