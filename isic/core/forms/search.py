from django import forms

from isic.core.search import build_elasticsearch_query


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
        collections = None
        if 'collections' in self.cleaned_data and self.cleaned_data['collections'].exists():
            collections = self.cleaned_data['collections']

        self.results = build_elasticsearch_query(
            self.cleaned_data.get('search', ''), self.user, collections
        )

        return super().clean()
