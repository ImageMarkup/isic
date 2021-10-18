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
