import pytest
from pytest_lazyfixture import lazy_fixture


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client_user,client,status',
    [
        [None, lazy_fixture('api_client'), 401],
        [lazy_fixture('user'), lazy_fixture('authenticated_api_client'), 200],
        [lazy_fixture('staff_user'), lazy_fixture('staff_api_client'), 200],
    ],
)
def test_core_api_user_me(client_user, client, status):
    r = client.get('/api/v2/users/me/')
    assert r.status_code == status, r.data
    if status == 200:
        assert r.data['id'] == client_user.pk
