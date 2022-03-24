from django.db.models.query import QuerySet
import django_filters
from django_filters.filters import BooleanFilter

from isic.core.models.collection import Collection


class CollectionFilter(django_filters.FilterSet):
    class Meta:
        model = Collection
        fields = [
            'official',
            'shared_with_me',
            'mine',
        ]

    official = BooleanFilter(method='filter_official')
    shared_with_me = BooleanFilter(method='filter_shared_with_me')
    mine = BooleanFilter(method='filter_mine')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)

    def filter_official(self, qs: QuerySet, name, value):
        qs = qs.filter(official=value)
        return qs

    def filter_shared_with_me(self, qs: QuerySet, name, value):
        if value is True and self.user.is_authenticated:
            qs = qs.filter(shares=self.user)

        return qs

    def filter_mine(self, qs: QuerySet, name, value):
        if value is True and self.user.is_authenticated:
            qs = qs.filter(creator=self.user)

        return qs
