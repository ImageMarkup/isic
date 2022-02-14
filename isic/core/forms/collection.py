import logging

from django import forms

from isic.core.models.collection import Collection

logger = logging.getLogger(__name__)


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description', 'public']
