import django_filters
from django_filters.widgets import LinkWidget

from isic.ingest.models import Accession


class AccessionFilter(django_filters.FilterSet):
    class Meta:
        model = Accession
        fields = ['status', 'review_status']

    status = django_filters.ChoiceFilter(choices=Accession.Status.choices, widget=LinkWidget())
    review_status = django_filters.ChoiceFilter(
        choices=Accession.ReviewStatus.choices, widget=LinkWidget()
    )
