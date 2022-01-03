from urllib.parse import parse_qs, urlparse

from django.urls.base import reverse
import pytest


@pytest.fixture
def random_images(image_factory):
    image_factory(accession__metadata={'diagnosis': 'melanoma'}, public=True)
    image_factory(accession__metadata={'diagnosis': 'nevus'}, public=True)


@pytest.mark.django_db
def test_zip_download(authenticated_api_client, random_images):
    r = authenticated_api_client.post(
        reverse('zip-download/api/url'), {'query': 'diagnosis:melanoma'}
    )
    assert r.status_code == 200, r.data
    parsed_url = urlparse(r.data)
    token = parse_qs(parsed_url.query)['zsid']
    r = authenticated_api_client.get(
        reverse('zip-download/api/file-descriptor'), data={'token': token[0]}
    )
    assert r.status_code == 200, r.json()
    assert len(r.json()['files']) == 1
