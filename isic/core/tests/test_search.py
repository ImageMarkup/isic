import pytest

from isic.core.search import add_to_search_index, get_elasticsearch_client


@pytest.fixture
def searchable_images(image_factory, search_index):
    images = [
        image_factory(public=True, accession__metadata={'diagnosis': 'melanoma'}),
        image_factory(public=False, accession__metadata={'diagnosis': 'nevus'}),
    ]
    for image in images:
        add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index='_all')

    return images


@pytest.mark.django_db
def test_core_api_image_search(searchable_images, staff_api_client):
    r = staff_api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 2

    r = staff_api_client.get('/api/v2/images/search/', {'query': 'diagnosis:nevus'})
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1
