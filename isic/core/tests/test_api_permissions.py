import pytest


@pytest.fixture
def images(image_factory):
    return [
        image_factory(public=True),
        image_factory(public=False),
    ]


@pytest.fixture
def private_image(image_factory):
    return image_factory(public=False)


@pytest.mark.django_db
def test_core_api_image_list(images, api_client, authenticated_api_client, staff_api_client):
    for client in [api_client, authenticated_api_client]:
        r = client.get('/api/v2/images/')
        assert r.status_code == 200, r.data
        assert r.data['count'] == 1
        assert {x['public'] for x in r.data['results']} == {True}

    r = staff_api_client.get('/api/v2/images/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 2


@pytest.mark.django_db
def test_core_api_image_list_private(private_image, authenticated_api_client):
    r = authenticated_api_client.get('/api/v2/images/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 0


@pytest.mark.django_db
def test_core_api_image_list_contributed(private_image, authenticated_api_client, user):
    private_image.accession.upload.cohort.contributor.owners.add(user)

    r = authenticated_api_client.get('/api/v2/images/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
def test_core_api_image_list_shares(private_image, authenticated_api_client, user):
    private_image.shares.add(user, through_defaults={'creator': user})
    private_image.save()

    r = authenticated_api_client.get('/api/v2/images/')
    assert r.status_code == 200, r.data
    assert r.data['count'] == 1


@pytest.mark.django_db
def test_core_api_image_detail(images, authenticated_api_client, staff_api_client):
    public_image_id = images[0].isic_id
    private_image_id = images[1].isic_id

    r = authenticated_api_client.get(f'/api/v2/images/{public_image_id}/')
    assert r.status_code == 200, r.data
    r = authenticated_api_client.get(f'/api/v2/images/{private_image_id}/')
    assert r.status_code == 404, r.data

    r = staff_api_client.get(f'/api/v2/images/{public_image_id}/')
    assert r.status_code == 200, r.data
    r = staff_api_client.get(f'/api/v2/images/{private_image_id}/')
    assert r.status_code == 200, r.data
