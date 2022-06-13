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


@pytest.mark.django_db(transaction=True)
def test_core_api_collection_populate_from_search(
    eager_celery, authenticated_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user, public=True)
    image_factory(accession__metadata={'sex': 'male'}, public=True)
    image_factory(accession__metadata={'sex': 'female'}, public=True)
    r = authenticated_client.post(
        f'/api/v2/collections/{collection.pk}/populate-from-search/', {'query': 'sex:male'}
    )

    assert r.status_code == 202, r.data
    assert collection.images.count() == 1
    assert collection.images.first().accession.metadata['sex'] == 'male'


@pytest.mark.django_db
@pytest.mark.parametrize(
    'endpoint,data',
    [
        ['populate-from-search', {'query': 'sex:male'}],
        ['populate-from-list', {'isic_ids': ['ISIC_0000000']}],
        ['remove-from-list', {'isic_ids': ['ISIC_0000000']}],
    ],
)
def test_core_api_collection_modify_locked(endpoint, data, staff_client, collection_factory, user):
    collection = collection_factory(locked=True, creator=user)

    r = staff_client.post(f'/api/v2/collections/{collection.pk}/{endpoint}/', data)

    assert r.status_code == 409, r.data


@pytest.mark.django_db
def test_core_api_collection_populate_from_list(
    authenticated_api_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user, public=True)
    public_image = image_factory(accession__metadata={'sex': 'male'}, public=True)
    private_image_shared = image_factory(accession__metadata={'sex': 'female'}, public=False)
    private_image_unshared = image_factory(accession__metadata={'sex': 'female'}, public=False)

    private_image_shared.shares.add(
        user, through_defaults={'creator': private_image_shared.accession.creator}
    )

    r = authenticated_api_client.post(
        f'/api/v2/collections/{collection.pk}/populate-from-list/',
        {
            'isic_ids': [
                public_image.isic_id,
                private_image_shared.isic_id,
                private_image_unshared.isic_id,
                'ISIC_0000000',
            ]
        },
    )

    assert r.status_code == 200, r.json()
    assert set(r.json()['no_perms_or_does_not_exist']) == {
        private_image_unshared.isic_id,
        'ISIC_0000000',
    }
    assert r.json()['private_image_public_collection'] == [private_image_shared.isic_id]
    assert r.json()['succeeded'] == [public_image.isic_id]


@pytest.mark.django_db
def test_core_api_collection_remove_from_list(
    authenticated_api_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user, public=False)
    public_image = image_factory(accession__metadata={'sex': 'male'}, public=True)
    private_image_shared = image_factory(accession__metadata={'sex': 'female'}, public=False)
    private_image_unshared = image_factory(accession__metadata={'sex': 'female'}, public=False)

    private_image_shared.shares.add(
        user, through_defaults={'creator': private_image_shared.accession.creator}
    )

    collection.images.add(public_image, private_image_shared, private_image_unshared)

    r = authenticated_api_client.post(
        f'/api/v2/collections/{collection.pk}/remove-from-list/',
        {
            'isic_ids': [
                public_image.isic_id,
                private_image_shared.isic_id,
                private_image_unshared.isic_id,
                'ISIC_0000000',
            ]
        },
    )

    assert r.status_code == 200, r.json()
    assert set(r.json()['no_perms_or_does_not_exist']) == {
        private_image_unshared.isic_id,
        'ISIC_0000000',
    }
    assert set(r.json()['succeeded']) == {public_image.isic_id, private_image_shared.isic_id}
