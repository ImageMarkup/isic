import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "contributors_", "num_visible"),
    [
        (lf("client"), lf("contributors"), 0),
        (
            lf("authenticated_client"),
            lf("contributors"),
            1,
        ),
        (lf("staff_client"), lf("contributors"), 2),
    ],
    ids=[
        "guest",
        "user",
        "staff",
    ],
)
def test_core_api_contributor_list_permissions(client_, contributors_, num_visible):
    r = client_.get("/api/v2/contributors/")

    assert r.status_code == 200, r.json()
    assert r.json()["count"] == num_visible


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "contributor_", "visible"),
    [
        (lf("client"), lf("contributor"), False),
        (lf("client"), lf("other_contributor"), False),
        (lf("authenticated_client"), lf("contributor"), True),
        (
            lf("authenticated_client"),
            lf("other_contributor"),
            False,
        ),
        (lf("staff_client"), lf("contributor"), True),
        (lf("staff_client"), lf("other_contributor"), True),
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
def test_core_api_contributor_detail_permissions(client_, contributor_, visible):
    r = client_.get(f"/api/v2/contributors/{contributor_.pk}/")

    if visible:
        assert r.status_code == 200, r.json()
        assert r.json()["id"] == contributor_.id
    else:
        assert r.status_code == 404, r.json()


@pytest.mark.django_db()
def test_core_api_contributor_create(authenticated_client, user):
    r = authenticated_client.post(
        "/api/v2/contributors/",
        data={
            "institution_name": "string",
            "institution_url": "http://google.com",
            "legal_contact_info": "string",
            "default_copyright_license": "CC-0",
            "default_attribution": "string",
        },
        content_type="application/json",
    )
    assert r.status_code == 201, r.json()
    assert r.json()["creator"] == user.pk
    assert r.json()["owners"] == [user.pk]
