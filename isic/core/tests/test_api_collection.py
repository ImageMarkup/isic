from django.urls import reverse
import pytest


@pytest.fixture()
def collections(public_collection, private_collection):
    return [public_collection, private_collection]


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "colls", "num_visible"),
    [
        (pytest.lazy_fixture("client"), pytest.lazy_fixture("collections"), 1),
        (
            pytest.lazy_fixture("authenticated_client"),
            pytest.lazy_fixture("collections"),
            1,
        ),
        (pytest.lazy_fixture("staff_client"), pytest.lazy_fixture("collections"), 2),
    ],
    ids=[
        "guest",
        "user",
        "staff",
    ],
)
def test_core_api_collection_list_permissions(client_, colls, num_visible):
    r = client_.get("/api/v2/collections/")

    assert r.status_code == 200, r.json()
    assert r.json()["count"] == num_visible


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "collection", "visible"),
    [
        (pytest.lazy_fixture("client"), pytest.lazy_fixture("public_collection"), True),
        (
            pytest.lazy_fixture("authenticated_client"),
            pytest.lazy_fixture("public_collection"),
            True,
        ),
        (
            pytest.lazy_fixture("staff_client"),
            pytest.lazy_fixture("public_collection"),
            True,
        ),
        (
            pytest.lazy_fixture("client"),
            pytest.lazy_fixture("private_collection"),
            False,
        ),
        (
            pytest.lazy_fixture("authenticated_client"),
            pytest.lazy_fixture("private_collection"),
            False,
        ),
        (
            pytest.lazy_fixture("staff_client"),
            pytest.lazy_fixture("private_collection"),
            True,
        ),
    ],
    ids=[
        "guest-public",
        "user-public",
        "staff-public",
        "guest-private",
        "user-private",
        "staff-private",
    ],
)
def test_core_api_collection_detail_permissions(client_, collection, visible):
    r = client_.get(f"/api/v2/collections/{collection.pk}/")

    if visible:
        assert r.status_code == 200, r.json()
        assert r.json()["id"] == collection.id
    else:
        assert r.status_code == 404, r.json()


@pytest.mark.django_db()
@pytest.mark.usefixtures("_eager_celery")
def test_core_api_collection_populate_from_search(
    authenticated_client,
    collection_factory,
    image_factory,
    user,
    django_capture_on_commit_callbacks,
):
    collection = collection_factory(locked=False, creator=user, public=True)
    image_factory(accession__sex="male", public=True)
    image_factory(accession__sex="female", public=True)

    with django_capture_on_commit_callbacks(execute=True):
        r = authenticated_client.post(
            f"/api/v2/collections/{collection.pk}/populate-from-search/",
            {"query": "sex:male"},
            content_type="application/json",
        )

    assert r.status_code == 202, r.json()
    assert collection.images.count() == 1
    assert collection.images.first().accession.metadata["sex"] == "male"


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("endpoint", "data"),
    [
        ("populate-from-search", {"query": "sex:male"}),
        ("populate-from-list", {"isic_ids": ["ISIC_0000000"]}),
        ("remove-from-list", {"isic_ids": ["ISIC_0000000"]}),
    ],
)
def test_core_api_collection_modify_locked(endpoint, data, staff_client, collection_factory, user):
    collection = collection_factory(locked=True, creator=user)

    r = staff_client.post(
        f"/api/v2/collections/{collection.pk}/{endpoint}/",
        data,
        content_type="application/json",
    )

    assert r.status_code == 409, r.json()


@pytest.mark.django_db()
def test_core_api_collection_populate_from_list(
    authenticated_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user, public=True)
    public_image = image_factory(accession__sex="male", public=True)
    private_image_shared = image_factory(accession__sex="female", public=False)
    private_image_unshared = image_factory(accession__sex="female", public=False)

    private_image_shared.shares.add(
        user, through_defaults={"grantor": private_image_shared.accession.creator}
    )

    r = authenticated_client.post(
        f"/api/v2/collections/{collection.pk}/populate-from-list/",
        {
            "isic_ids": [
                public_image.isic_id,
                private_image_shared.isic_id,
                private_image_unshared.isic_id,
                "ISIC_0000000",
            ]
        },
        content_type="application/json",
    )

    assert r.status_code == 200, r.json()
    assert set(r.json()["no_perms_or_does_not_exist"]) == {
        private_image_unshared.isic_id,
        "ISIC_0000000",
    }
    assert r.json()["private_image_public_collection"] == [private_image_shared.isic_id]
    assert r.json()["succeeded"] == [public_image.isic_id]


@pytest.mark.django_db()
def test_core_api_collection_remove_from_list(
    authenticated_client, collection_factory, image_factory, user
):
    collection = collection_factory(locked=False, creator=user, public=False)
    public_image = image_factory(accession__sex="male", public=True)
    private_image_shared = image_factory(accession__sex="female", public=False)
    private_image_unshared = image_factory(accession__sex="female", public=False)

    private_image_shared.shares.add(
        user, through_defaults={"grantor": private_image_shared.accession.creator}
    )

    collection.images.add(public_image, private_image_shared, private_image_unshared)

    r = authenticated_client.post(
        f"/api/v2/collections/{collection.pk}/remove-from-list/",
        {
            "isic_ids": [
                public_image.isic_id,
                private_image_shared.isic_id,
                private_image_unshared.isic_id,
                "ISIC_0000000",
            ]
        },
        content_type="application/json",
    )

    assert r.status_code == 200, r.json()
    assert set(r.json()["no_perms_or_does_not_exist"]) == {
        private_image_unshared.isic_id,
        "ISIC_0000000",
    }
    assert set(r.json()["succeeded"]) == {
        public_image.isic_id,
        private_image_shared.isic_id,
    }


@pytest.mark.django_db()
@pytest.mark.usefixtures("_eager_celery")
def test_core_api_collection_share(
    staff_client, collection, user, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("api:collection_share_to_users", args=[collection.pk]),
            {
                "user_ids": [user.pk],
            },
            content_type="application/json",
        )

    assert r.status_code == 202, r.json()

    assert user in collection.shares.all()
