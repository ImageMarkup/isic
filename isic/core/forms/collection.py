import logging

from django import forms

from isic.core.models.collection import Collection

logger = logging.getLogger(__name__)


class CollectionForm(forms.Form):
    fields = forms.fields_for_model(Collection)

    name = fields["name"]
    description = fields["description"]
    public = fields["public"]
