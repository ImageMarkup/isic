from django.db.models.aggregates import Count
import django_filters
from django_filters.filters import ChoiceFilter

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
        fields = ['diagnosis']

    def __init__(self, data=None, queryset=None, *, cohort, request=None, prefix=None):
        super().__init__(data=data, queryset=queryset, request=request, prefix=prefix)

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

    diagnosis = DynamicChoiceFilter(
        label='Diagnosis', method='filter_metadata_value', choices_from='diagnosis_choices'
    )

    def filter_metadata_value(self, queryset, name, value):
        return queryset.filter(**{f'metadata__{name}': value})
