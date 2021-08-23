import pytest
import requests

from isic.core.search import add_to_search_index, get_elasticsearch_client


@pytest.fixture
def searchable_image(search_index, image_factory):
    image = image_factory(accession__metadata={'age': 52}, public=True)
    add_to_search_index(image)
    # Ensure that the image is available in the index for search
    get_elasticsearch_client().indices.refresh(index='_all')
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


@pytest.mark.django_db
def test_api_image_urls_thumbnail_256(api_client, image_factory):
    image = image_factory(public=True)

    api_resp = api_client.get(f'/api/v2/images/{image.isic_id}/')

    assert isinstance(api_resp.data.get('urls'), dict)
    assert isinstance(api_resp.data['urls'].get('thumbnail_256'), str)
    thumbnail_url = api_resp.data['urls']['thumbnail_256']
    assert thumbnail_url

    # "stream=True", as there's no need to download the actual response body
    storage_resp = requests.get(thumbnail_url, stream=True)
    assert storage_resp.status_code == 200
    # TODO: MinioStorage doesn't respect FieldFile.content_type, so there's no point to this
    # assertion, even though it succeeds
    # assert storage_resp.headers['Content-Type'] == 'image/jpeg'
    # TODO: Fix Content-Disposition
    # assert 'thumbnail' in storage_resp.headers['Content-Disposition']


@pytest.mark.django_db
def test_api_image_urls_full(api_client, image_factory):
    image = image_factory(public=True)

    api_resp = api_client.get(f'/api/v2/images/{image.isic_id}/')

    assert isinstance(api_resp.data.get('urls'), dict)
    assert isinstance(api_resp.data['urls'].get('full'), str)
    full_url = api_resp.data['urls']['full']
    assert full_url

    # "stream=True", as there's no need to download the actual response body
    storage_resp = requests.get(full_url, stream=True)
    assert storage_resp.status_code == 200
