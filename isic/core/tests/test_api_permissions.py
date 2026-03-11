from django.urls import reverse
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
        r = client_.get(reverse("api:image_list"))
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1
        assert {x["public"] for x in r.json()["results"]} == {True}

    r = staff_client.get(reverse("api:image_list"))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 2


@pytest.mark.django_db
def test_core_api_image_list_private(private_image, authenticated_client):
    r = authenticated_client.get(reverse("api:image_list"))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 0


@pytest.mark.django_db
def test_core_api_image_list_contributed(private_image, authenticated_client, user):
    private_image.accession.cohort.contributor.owners.add(user)

    r = authenticated_client.get(reverse("api:image_list"))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


@pytest.mark.django_db
def test_core_api_image_list_shares(private_image, authenticated_client, user, staff_user):
    private_image.shares.add(user, through_defaults={"grantor": staff_user})
    private_image.save()

    r = authenticated_client.get(reverse("api:image_list"))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


# Can be removed once https://github.com/ImageMarkup/tracker/issues/77 is resolved
@pytest.mark.django_db
def test_core_api_image_list_no_duplicates(private_image, authenticated_client, user, staff_user):
    private_image.accession.cohort.contributor.owners.add(user)
    private_image.shares.add(user, through_defaults={"grantor": staff_user})
    private_image.save()

    r = authenticated_client.get(reverse("api:image_list"))
    assert r.status_code == 200, r.json()
    assert r.json()["count"] == 1


@pytest.mark.django_db
def test_core_api_image_detail(images, authenticated_client, staff_client):
    public_image_id = images[0].isic_id
    private_image_id = images[1].isic_id

    public_url = reverse("api:image_detail", kwargs={"isic_id": public_image_id})
    private_url = reverse("api:image_detail", kwargs={"isic_id": private_image_id})

    r = authenticated_client.get(public_url)
    assert r.status_code == 200, r.json()
    r = authenticated_client.get(private_url)
    assert r.status_code == 404, r.json()

    r = staff_client.get(public_url)
    assert r.status_code == 200, r.json()
    r = staff_client.get(private_url)
    assert r.status_code == 200, r.json()


@pytest.mark.django_db
def test_api_auth_staff_user(authenticated_client, staff_client, metadata_file):
    url = reverse("api:metadata_file_delete", kwargs={"id": metadata_file.pk})
    r = authenticated_client.delete(url)
    assert r.status_code == 401, r.json()

    r = staff_client.delete(url)
    assert r.status_code == 204, r.json()


@pytest.mark.django_db
def test_api_collection_share_to_users(authenticated_client, collection):
    r = authenticated_client.post(
        reverse("api:collection_share_to_users", kwargs={"id": collection.pk}),
        {"user_ids": []},
        content_type="application/json",
    )
    assert r.status_code == 403, r.json()
