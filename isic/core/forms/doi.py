from typing import TYPE_CHECKING

from django import forms

from isic.core.services.collection.doi import (
    collection_check_create_doi_allowed,
    collection_create_doi,
)

if TYPE_CHECKING:
    from isic.core.models.collection import Collection


class CreateDoiForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        self.collection: Collection = kwargs.pop("collection", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        collection_check_create_doi_allowed(user=self.request.user, collection=self.collection)

    def save(self):
        collection_create_doi(user=self.request.user, collection=self.collection)
