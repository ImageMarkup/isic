import logging

from django import forms
from django.core.exceptions import ValidationError

from isic.core.models.collection import Collection

logger = logging.getLogger(__name__)


class CollectionForm(forms.ModelForm):
    class Meta:
        model = Collection
        fields = ['name', 'description', 'public']

    def clean_public(self) -> bool:
        value: bool = self.cleaned_data['public']

        if self.instance and value:
            has_private_images = self.instance.images.filter(public=False).exists()
            if has_private_images:
                raise ValidationError("Can't make collection public, it contains private images.")

        return value
