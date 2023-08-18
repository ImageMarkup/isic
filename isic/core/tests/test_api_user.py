import pytest
from pytest_lazyfixture import lazy_fixture


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_user,client_,status",
    [
        [None, lazy_fixture("client"), 401],
        [lazy_fixture("user"), lazy_fixture("authenticated_client"), 200],
        [lazy_fixture("staff_user"), lazy_fixture("staff_client"), 200],
    ],
)
def test_core_api_user_me(client_user, client_, status):
    r = client_.get("/api/v2/users/me/")
    assert r.status_code == status, r.json()
    if status == 200:
        assert r.json()["id"] == client_user.pk


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_user,client_,status",
    [
        [None, lazy_fixture("client"), 401],
        [lazy_fixture("user"), lazy_fixture("authenticated_client"), 200],
        [lazy_fixture("staff_user"), lazy_fixture("staff_client"), 200],
    ],
)
def test_core_api_user_accept_terms(client_user, client_, status):
    r = client_.put("/api/v2/users/accept-terms/", content_type="application/json")
    assert r.status_code == status, r.json()

    if status == 200:
        client_user.refresh_from_db()
        assert client_user.profile.accepted_terms
