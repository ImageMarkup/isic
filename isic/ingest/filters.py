import django_filters
from django_filters.widgets import LinkWidget

from isic.ingest.models import Accession
from isic.ingest.validators import DiagnosisEnum


class AccessionFilter(django_filters.FilterSet):
    class Meta:
        model = Accession
        fields = ['status', 'review_status', 'diagnosis']

    status = django_filters.ChoiceFilter(choices=Accession.Status.choices, widget=LinkWidget())
    review_status = django_filters.ChoiceFilter(
        choices=Accession.ReviewStatus.choices,
        widget=LinkWidget(),
        null_label='Unreviewed',
    )
    diagnosis = django_filters.ChoiceFilter(
        choices=sorted([(x.value, x.value) for x in DiagnosisEnum]),
        label='Diagnosis',
        method='filter_metadata_value',
    )

    def filter_metadata_value(self, queryset, name, value):
        return queryset.filter(**{f'metadata__{name}': value})
