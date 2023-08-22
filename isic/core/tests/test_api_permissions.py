import pytest


@pytest.fixture
def images(image_factory):
    return [
        image_factory(public=True),
        image_factory(public=False),
    ]


@pytest.mark.django_db
def test_core_api_image_list(images, client, authenticated_client, staff_client):
    for client_ in [client, authenticated_client]:
        r = client_.get("/api/v2/images/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1
        assert {x["public"] for x in r.json()["results"]} == {True}

    r = staff_client.get("/api/v2/images/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 2


@pytest.mark.django_db
def test_core_api_image_list_private(private_image, authenticated_client):
    r = authenticated_client.get("/api/v2/images/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 0


@pytest.mark.django_db
def test_core_api_image_list_contributed(private_image, authenticated_client, user):
    private_image.accession.cohort.contributor.owners.add(user)

    r = authenticated_client.get("/api/v2/images/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


@pytest.mark.django_db
def test_core_api_image_list_shares(private_image, authenticated_client, user, staff_user):
    private_image.shares.add(user, through_defaults={"creator": staff_user})
    private_image.save()

    r = authenticated_client.get("/api/v2/images/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


# Can be removed once https://github.com/ImageMarkup/tracker/issues/77 is resolved
@pytest.mark.django_db
def test_core_api_image_list_no_duplicates(private_image, authenticated_client, user, staff_user):
    private_image.accession.cohort.contributor.owners.add(user)
    private_image.shares.add(user, through_defaults={"creator": staff_user})
    private_image.save()

    r = authenticated_client.get("/api/v2/images/")
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


@pytest.mark.django_db
def test_core_api_image_detail(images, authenticated_client, staff_client):
    public_image_id = images[0].isic_id
    private_image_id = images[1].isic_id

    r = authenticated_client.get(f"/api/v2/images/{public_image_id}/")
    assert r.status_code == 200, r.json()
    r = authenticated_client.get(f"/api/v2/images/{private_image_id}/")
    assert r.status_code == 404, r.json()

    r = staff_client.get(f"/api/v2/images/{public_image_id}/")
    assert r.status_code == 200, r.json()
    r = staff_client.get(f"/api/v2/images/{private_image_id}/")
    assert r.status_code == 200, r.json()


@pytest.mark.django_db
def test_api_auth_staff_user(authenticated_client, staff_client, metadata_file):
    r = authenticated_client.delete(f"/api/v2/metadata-files/{metadata_file.pk}/")
    assert r.status_code == 401, r.json()

    r = staff_client.delete(f"/api/v2/metadata-files/{metadata_file.pk}/")
    assert r.status_code == 204, r.json()
