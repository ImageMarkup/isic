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


@pytest.fixture
def private_and_public_images_collections(search_index, image_factory, collection_factory):
    public_coll, private_coll = collection_factory(public=True), collection_factory(public=False)
    public_image, private_image = image_factory(public=True), image_factory(public=False)

    public_coll.images.add(public_image)
    private_coll.images.add(private_image)

    for image in [public_image, private_image]:
        add_to_search_index(image)

    get_elasticsearch_client().indices.refresh(index='_all')

    yield public_coll, private_coll


@pytest.fixture
def collection_with_image(search_index, image_factory, collection_factory):
    public_coll = collection_factory(public=True)
    public_image = image_factory(public=True, accession__metadata={'age': 52})
    public_coll.images.add(public_image)
    add_to_search_index(public_image)
    get_elasticsearch_client().indices.refresh(index='_all')
    yield public_coll


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
def test_core_api_image_search_private_image_as_guest(private_searchable_image, api_client):
    r = api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 0


@pytest.mark.django_db
def test_core_api_image_search_images_as_guest(searchable_images, api_client):
    r = api_client.get('/api/v2/images/search/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
def test_core_api_image_search_contributed(
    private_searchable_image, authenticated_api_client, user
):
    private_searchable_image.accession.cohort.contributor.owners.add(user)
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


@pytest.mark.django_db
def test_core_api_image_search_collection_and_query(
    collection_with_image, authenticated_api_client
):
    r = authenticated_api_client.get(
        '/api/v2/images/search/',
        {'collections': f'{collection_with_image.pk}', 'query': 'age_approx:50'},
    )
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    'collection_is_public,image_is_public,can_see',
    [
        (True, True, True),
        # Don't leak which images are in a private collection
        (False, True, False),
        (False, False, False),
    ],
    ids=['all-public', 'private-coll-public-image', 'all-private'],
)
def test_core_api_image_search_collection(
    authenticated_api_client,
    image_factory,
    collection_factory,
    search_index,
    collection_is_public,
    image_is_public,
    can_see,
):
    collection = collection_factory(public=collection_is_public)
    image = image_factory(public=image_is_public)
    collection.images.add(image)
    add_to_search_index(image)
    get_elasticsearch_client().indices.refresh(index='_all')

    r = authenticated_api_client.get('/api/v2/images/search/', {'collections': str(collection.pk)})
    assert r.status_code == 200, r.data

    if can_see:
        assert r.data['count'] == 1
    else:
        assert r.data['count'] == 0


@pytest.mark.django_db
def test_core_api_image_search_collection_parsing(
    private_and_public_images_collections, authenticated_api_client
):
    public_coll, private_coll = private_and_public_images_collections

    r = authenticated_api_client.get(
        '/api/v2/images/search/', {'collections': f'{public_coll.pk},{private_coll.pk}'}
    )
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
def test_core_api_image_faceting_collections(
    private_and_public_images_collections, authenticated_api_client
):
    public_coll, private_coll = private_and_public_images_collections

    r = authenticated_api_client.get(
        '/api/v2/images/facets/', {'collections': f'{public_coll.pk},{private_coll.pk}'}
    )
    assert r.status_code == 200, r.data
    buckets = r.data['collections']['buckets']
    assert len(buckets) == 1
    assert buckets[0] == {'key': public_coll.pk, 'doc_count': 1}


@pytest.mark.django_db
def test_core_api_image_faceting(private_and_public_images_collections, authenticated_api_client):
    public_coll, private_coll = private_and_public_images_collections

    r = authenticated_api_client.get(
        '/api/v2/images/facets/',
    )
    assert r.status_code == 200, r.data
    buckets = r.data['collections']['buckets']
    assert len(buckets) == 1, buckets
    assert buckets[0] == {'key': public_coll.pk, 'doc_count': 1}, buckets
