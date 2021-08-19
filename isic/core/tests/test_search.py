import itertools

import pytest

from isic.core.models.image import RESTRICTED_SEARCH_FIELDS
from isic.core.search import add_to_search_index, get_elasticsearch_client


@pytest.fixture
def private_searchable_image(image_factory, search_index):
    image = image_factory(public=False)
    add_to_search_index(image)

    # Ensure that the images are available in the index for search
    get_elasticsearch_client().indices.refresh(index='_all')

    return image


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


@pytest.fixture
def searchable_images_with_private_fields(image_factory, search_index):
    images = [
        image_factory(public=True, accession__metadata={'age': 50}),
        image_factory(public=True, accession__metadata={'patient_id': 'IP_1234567'}),
        image_factory(public=True, accession__metadata={'lesion_id': 'IL_1234567'}),
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


@pytest.mark.django_db
def test_core_api_image_search_private_image(private_searchable_image, authenticated_api_client):
    r = authenticated_api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 0


@pytest.mark.django_db
def test_core_api_image_search_contributed(
    private_searchable_image, authenticated_api_client, user
):
    private_searchable_image.accession.upload.cohort.contributor.owners.add(user)
    add_to_search_index(private_searchable_image)
    get_elasticsearch_client().indices.refresh(index='_all')

    r = authenticated_api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
def test_core_api_image_search_shares(private_searchable_image, authenticated_api_client, user):
    private_searchable_image.shares.add(user, through_defaults={'creator': user})
    private_searchable_image.save()
    add_to_search_index(private_searchable_image)
    get_elasticsearch_client().indices.refresh(index='_all')

    r = authenticated_api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    'restricted_field,route',
    itertools.product(RESTRICTED_SEARCH_FIELDS, ['/api/v2/images/', '/api/v2/images/search/']),
)
def test_core_api_image_hides_fields(
    authenticated_api_client, searchable_images_with_private_fields, restricted_field, route
):
    r = authenticated_api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 3
    for image in r.data['results']:
        assert restricted_field not in image['metadata']
