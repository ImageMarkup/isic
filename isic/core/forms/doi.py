import logging
import random

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
import requests
from requests.exceptions import HTTPError

from isic.core.models.collection import Collection
from isic.core.models.doi import Doi

logger = logging.getLogger(__name__)

DOI_PREFIX = '10.80222'


class CreateDoiForm(forms.Form):
    collection_pk = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        super().clean()
        self.collection = Collection.objects.get(pk=self.cleaned_data['collection_pk'])

        if not self.request.user.has_perm('core.create_doi', self.collection):
            raise ValidationError("You don't have permissions to do that.")
        elif not self.collection.public:
            raise ValidationError('A collection must be public to issue a DOI.')
        elif self.collection.doi:
            raise ValidationError('This collection already has a DOI.')
        elif self.collection.images.filter(public=False).exists():
            raise ValidationError('This collection contains private images.')

    def _create_doi(self) -> str:
        doi_id = f'{DOI_PREFIX}/{random.randint(10_000,999_999)}'

        doi = self.collection.as_datacite_doi(self.request.user, doi_id)

        r = requests.post(
            f'{settings.ISIC_DATACITE_API_URL}/dois',
            auth=(settings.ISIC_DATACITE_USERNAME, settings.ISIC_DATACITE_PASSWORD),
            timeout=5,
            json=doi,
        )
        # TODO: check for already exists
        r.raise_for_status()
        return doi_id

    def save(self):
        try:
            id = self._create_doi()
        except HTTPError as e:
            logger.error(e)
            raise ValidationError('Something went wrong talking to DataCite.')
        else:
            with transaction.atomic():
                self.collection.doi = Doi.objects.create(id=id, url=f'https://doi.org/{id}')
                self.collection.save(update_fields=['doi'])
