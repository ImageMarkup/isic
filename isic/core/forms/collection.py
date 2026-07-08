import logging

from django import forms

from isic.core.models.collection import Collection, CollectionTag
from isic.core.widgets import ComboboxWidget

logger = logging.getLogger(__name__)


class CollectionForm(forms.Form):
    fields = forms.fields_for_model(Collection)

    name = fields["name"]
    description = fields["description"]
    public = fields["public"]
    tags = forms.ModelMultipleChoiceField(
        required=False,
        queryset=CollectionTag.objects.all(),
        widget=ComboboxWidget(
            queryset=CollectionTag.objects.all(),
            lookup_field="tag",
            attrs={"placeholder": "Select Tags"},
        ),
    )
