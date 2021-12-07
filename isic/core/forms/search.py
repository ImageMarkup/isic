from django import forms
from django.db.models.query import QuerySet

from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects


class ImageSearchForm(forms.Form):
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'diagnosis:melanoma OR diagnosis:nevus'}),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        collections = kwargs.pop('collections')
        super().__init__(*args, **kwargs)
        self.fields['collections'] = forms.ModelMultipleChoiceField(
            queryset=collections, required=False
        )

    def clean(self):
        self.results: QuerySet[Image] = get_visible_objects(
            self.user,
            'core.view_image',
        )
        self.results = self.results.select_related('accession').from_search_query(
            self.cleaned_data.get('search', '')
        )

        if 'collections' in self.cleaned_data and self.cleaned_data['collections'].exists():
            self.results = self.results.filter(collections__in=self.cleaned_data['collections'])

        return super().clean()
