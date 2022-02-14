import pytest


@pytest.fixture
def collections(public_collection, private_collection):
    return [public_collection, private_collection]


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client,colls,num_visible',
    [
        [pytest.lazy_fixture('api_client'), pytest.lazy_fixture('collections'), 1],
        [
            pytest.lazy_fixture('authenticated_api_client'),
            pytest.lazy_fixture('collections'),
            1,
        ],
        [pytest.lazy_fixture('staff_api_client'), pytest.lazy_fixture('collections'), 2],
    ],
    ids=[
        'guest',
        'user',
        'staff',
    ],
)
def test_core_api_collection_list_permissions(client, colls, num_visible):
    r = client.get('/api/v2/collections/')

    assert r.status_code == 200, r.data
    assert r.data['count'] == num_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client,collection,visible',
    [
        [pytest.lazy_fixture('api_client'), pytest.lazy_fixture('public_collection'), True],
        [
            pytest.lazy_fixture('authenticated_api_client'),
            pytest.lazy_fixture('public_collection'),
            True,
        ],
        [pytest.lazy_fixture('staff_api_client'), pytest.lazy_fixture('public_collection'), True],
        [pytest.lazy_fixture('api_client'), pytest.lazy_fixture('private_collection'), False],
        [
            pytest.lazy_fixture('authenticated_api_client'),
            pytest.lazy_fixture('private_collection'),
            False,
        ],
        [pytest.lazy_fixture('staff_api_client'), pytest.lazy_fixture('private_collection'), True],
    ],
    ids=[
        'guest-public',
        'user-public',
        'staff-public',
        'guest-private',
        'user-private',
        'staff-private',
    ],
)
def test_core_api_collection_detail_permissions(client, collection, visible):
    r = client.get(f'/api/v2/collections/{collection.pk}/')

    if visible:
        assert r.status_code == 200, r.data
        assert r.data['id'] == collection.id
    else:
        assert r.status_code == 404, r.data


@pytest.mark.django_db
def test_core_api_collection_populate_from_search(
    eager_celery, authenticated_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user)
    image_factory(accession__metadata={'sex': 'male'})
    image_factory(accession__metadata={'sex': 'female'})
    r = authenticated_client.post(
        f'/api/v2/collections/{collection.pk}/populate-from-search/', {'query': 'sex:male'}
    )

    assert r.status_code == 200, r.data
    assert collection.images.count() == 1
    assert collection.images.first().accession.metadata['sex'] == 'male'


@pytest.mark.django_db
def test_core_api_collection_populate_from_search_locked(
    authenticated_client, collection_factory, user
):
    collection = collection_factory(locked=True, creator=user)

    r = authenticated_client.post(
        f'/api/v2/collections/{collection.pk}/populate-from-search/', {'query': 'sex:male'}
    )

    assert r.status_code == 400, r.data
