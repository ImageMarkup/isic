from django.urls import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "contributors_", "num_visible"),
    [
        (lf("client"), lf("contributors"), None),
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
    r = client_.get(reverse("api:contributor_list"))

    if num_visible is None:
        assert r.status_code == 401, r.json()
    else:
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == num_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "contributor_", "expected_status"),
    [
        (lf("client"), lf("contributor"), 401),
        (lf("client"), lf("other_contributor"), 401),
        (lf("authenticated_client"), lf("contributor"), 200),
        (
            lf("authenticated_client"),
            lf("other_contributor"),
            404,
        ),
        (lf("staff_client"), lf("contributor"), 200),
        (lf("staff_client"), lf("other_contributor"), 200),
    ],
    ids=[
        "guest-contributor-1-unauthorized",
        "guest-contributor-2-unauthorized",
        "user-owner-contributor-1-visible",
        "user-non-owner-contributor-2-invisible",
        "staff-contributor-1-visible",
        "staff-contributor-2-visible",
    ],
)
def test_core_api_contributor_detail_permissions(client_, contributor_, expected_status):
    r = client_.get(reverse("api:contributor_detail", kwargs={"id": contributor_.pk}))

    assert r.status_code == expected_status, r.json()

    if expected_status == 200:
        assert r.json()["id"] == contributor_.id


@pytest.mark.django_db
def test_core_api_contributor_create(authenticated_client, user):
    r = authenticated_client.post(
        reverse("api:contributor_create"),
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
