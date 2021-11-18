from django import forms
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
import django_filters
from django_filters.filters import BooleanFilter, ChoiceFilter

from isic.ingest.models import Accession
from isic.ingest.models.accession import AccessionStatus


class TailwindSelectWidget(forms.widgets.Select):
    template_name = 'ingest/widgets/select.html'


class CheckFilter(django_filters.ChoiceFilter):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('null_value', 'unreviewed')
        kwargs.setdefault(
            'choices', [('unreviewed', 'Unreviewed'), (False, 'Rejected'), (True, 'Accepted')]
        )
        kwargs.setdefault('widget', TailwindSelectWidget)
        super().__init__(*args, **kwargs)


class AccessionFilter(django_filters.FilterSet):
    class Meta:
        model = Accession
        fields = [
            'status',
            'quality_check',
            'phi_check',
            'diagnosis_check',
            'duplicate_check',
            'lesion_check',
            'published',
        ]

    status = ChoiceFilter(choices=AccessionStatus.choices, widget=TailwindSelectWidget)
    quality_check = CheckFilter()
    phi_check = CheckFilter()
    diagnosis_check = CheckFilter()
    duplicate_check = CheckFilter()
    lesion_check = CheckFilter()
    published = BooleanFilter(
        method='filter_published',
        label='Published',
    )

    def filter_published(self, qs: QuerySet, name, value):
        if value is True:
            qs = qs.filter(~Q(image=None))
        elif value is False:
            qs = qs.filter(image=None)

        return qs
