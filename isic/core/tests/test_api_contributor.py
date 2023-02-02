import pytest
from pytest import lazy_fixture


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client,contributors_,num_visible",
    [
        [lazy_fixture("api_client"), lazy_fixture("contributors"), 0],
        [
            lazy_fixture("authenticated_api_client"),
            lazy_fixture("contributors"),
            1,
        ],
        [lazy_fixture("staff_api_client"), lazy_fixture("contributors"), 2],
    ],
    ids=[
        "guest",
        "user",
        "staff",
    ],
)
def test_core_api_contributor_list_permissions(client, contributors_, num_visible):
    r = client.get("/api/v2/contributors/")

    assert r.status_code == 200, r.data
    assert r.data["count"] == num_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client,contributor_,visible",
    [
        [lazy_fixture("api_client"), lazy_fixture("contributor"), False],
        [lazy_fixture("api_client"), lazy_fixture("other_contributor"), False],
        [lazy_fixture("authenticated_api_client"), lazy_fixture("contributor"), True],
        [lazy_fixture("authenticated_api_client"), lazy_fixture("other_contributor"), False],
        [lazy_fixture("staff_api_client"), lazy_fixture("contributor"), True],
        [lazy_fixture("staff_api_client"), lazy_fixture("other_contributor"), True],
    ],
    ids=[
        "guest-contributor-1-invisible",
        "guest-contributor-2-invisible",
        "user-owner-contributor-1-visible",
        "user-non-owner-contributor-2-invisible",
        "staff-contributor-1-visible",
        "staff-contributor-2-visible",
    ],
)
def test_core_api_contributor_detail_permissions(client, contributor_, visible):
    r = client.get(f"/api/v2/contributors/{contributor_.pk}/")

    if visible:
        assert r.status_code == 200, r.data
        assert r.data["id"] == contributor_.id
    else:
        assert r.status_code == 404, r.data


@pytest.mark.django_db
def test_core_api_contributor_create(authenticated_api_client, user):
    r = authenticated_api_client.post(
        "/api/v2/contributors/",
        data={
            "institution_name": "string",
            "institution_url": "http://google.com",
            "legal_contact_info": "string",
            "default_copyright_license": "CC-0",
            "default_attribution": "string",
        },
    )
    assert r.status_code == 201, r.data
    assert r.data["creator"] == user.pk
    assert r.data["owners"] == [user.pk]
