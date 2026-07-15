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
            option_type="tag",
            edit=True,
            info_text={
                "create": (
                    "Create a unique, informative, and succinct tag. "
                    "Others may use this tag on other Collections."
                ),
                "edit": (
                    "Are you sure you want to modify the name of this tag? "
                    "This tag will be changed for all Collections using it."
                ),
                "delete": (
                    "Are you sure you want to permanently delete this tag? "
                    "This tag will be removed from all Collections using it."
                ),
            },
        ),
    )
