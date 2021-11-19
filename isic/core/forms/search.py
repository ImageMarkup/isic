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

    def full_clean(self):
        super().full_clean()

        collections = (
            self.cleaned_data['collections'] if self.cleaned_data['collections'].exists() else None
        )
        self.results = build_elasticsearch_query(
            self.cleaned_data.get('search', ''), self.user, collections
        )
