from django.db.models.aggregates import Count
import django_filters
from django_filters.filters import ChoiceFilter
from django_filters.widgets import LinkWidget

from isic.ingest.models import Accession


class DynamicChoiceFilter(ChoiceFilter):
    def __init__(self, *args, **kwargs):
        self.choices_from = kwargs.pop('choices_from')
        super().__init__(*args, **kwargs)

    @property
    def field(self):
        if not hasattr(self, '_field'):
            field_kwargs = self.extra.copy()
            field_kwargs['choices'] = getattr(self.parent, self.choices_from)
            self._field = self.field_class(label=self.label, **field_kwargs)
        return self._field


class AccessionFilter(django_filters.FilterSet):
    class Meta:
        model = Accession
        fields = ['review_status', 'diagnosis']

    def __init__(self, data=None, queryset=None, *, cohort, request=None, prefix=None):
        super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)

        review_status_frequencies = dict(
            Accession.objects.filter(upload__cohort=cohort)
            .values('review_status')
            .order_by('review_status')
            .annotate(count=Count('*'))
            .values_list('review_status', 'count')
        )
        review_status_frequencies.setdefault(None, 0)

        self.review_status_choices = [('null', f'Unreviewed ({review_status_frequencies[None]})')]
        for key, label in Accession.ReviewStatus.choices:
            self.review_status_choices.append(
                (key, f'{label} ({review_status_frequencies.get(key, 0)})')
            )

        diagnosis_frequencies = (
            Accession.objects.filter(upload__cohort=cohort, metadata__diagnosis__isnull=False)
            .values('metadata__diagnosis')
            .order_by('metadata__diagnosis')
            .annotate(count=Count('metadata__diagnosis'))
            .values_list('metadata__diagnosis', 'count')
        )
        self.diagnosis_choices = [
            (diagnosis, f'{diagnosis} ({count})') for diagnosis, count in diagnosis_frequencies
        ]

    review_status = DynamicChoiceFilter(
        choices_from='review_status_choices',
        widget=LinkWidget(),
        # null_label='Unreviewed',
    )
    diagnosis = DynamicChoiceFilter(
        label='Diagnosis', method='filter_metadata_value', choices_from='diagnosis_choices'
    )

    def filter_metadata_value(self, queryset, name, value):
        return queryset.filter(**{f'metadata__{name}': value})
