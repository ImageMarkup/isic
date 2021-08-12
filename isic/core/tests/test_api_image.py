from time import sleep

import pytest

from isic.core.search import add_to_search_index


@pytest.fixture
def searchable_image(search_index, image_factory):
    image = image_factory(accession__metadata={'age': 52}, public=True)
    add_to_search_index(image)
    sleep(1)  # TODO: see flakiness issue in other tests.
    return image


@pytest.mark.django_db
def test_core_api_image_ages_are_always_rounded(
    authenticated_api_client, staff_api_client, searchable_image
):
    for client in [authenticated_api_client, staff_api_client]:
        r = client.get('/api/v2/images/')
        assert r.status_code == 200, r.data
        assert r.data['count'] == 1
        assert r.data['results'][0]['metadata']['age_approx'] == 50

        r = client.get(f'/api/v2/images/{searchable_image.isic_id}/')
        assert r.status_code == 200, r.data
        assert r.data['metadata']['age_approx'] == 50

        # test search isn't leaking ages
        r = client.get('/api/v2/images/search/', {'query': 'age_approx:50'})
        assert r.status_code == 200, r.data
        assert r.data['count'] == 1
        assert r.data['results'][0]['metadata']['age_approx'] == 50

        r = client.get('/api/v2/images/search/', {'query': 'age_approx:52'})
        assert r.status_code == 200, r.data
        assert r.data['count'] == 0
