from django.contrib.auth.models import User
import pytest

from isic.login.girder import GirderBackend
from isic.login.models import Profile

# A girder compatible hashed version of 'testpassword'
TEST_PASSWORD_HASH = '$2b$12$BBLKZbXl/nEbjwSLwqJeJ.2tIsAbVfGoe.FWNCNLgppXIKSEJh.7e'


@pytest.fixture
def mocked_girder_user(mocker, girder_user_factory):
    girder_user = girder_user_factory(salt=TEST_PASSWORD_HASH)
    mocker.patch.object(Profile, 'fetch_girder_user', return_value=girder_user)
    yield girder_user


@pytest.mark.django_db
@pytest.mark.parametrize('existent', [False, True], ids=['nonexistent', 'existent'])
def test_authenticate_correct(existent, mocker, mocked_girder_user, user_factory):
    if existent:
        # Don't set a password here, we'll expect it to be changed
        user = user_factory(
            email=mocked_girder_user['email'], password=f'bcrypt_girder${mocked_girder_user["salt"]}'
        )
    set_password_spy = mocker.spy(User, 'set_password')

    authenticated_user = GirderBackend().authenticate(
        None, mocked_girder_user['email'], 'testpassword'
    )

    assert authenticated_user
    assert authenticated_user.email == mocked_girder_user['email']
    # It's critical that the "User.set_password" API is actually called, to ensure signals fire
    set_password_spy.assert_called_once()
    assert authenticated_user.check_password('testpassword')
    if existent:
        assert authenticated_user.id == user.id


@pytest.mark.django_db
@pytest.mark.parametrize('existent', [False, True], ids=['nonexistent', 'existent'])
def test_authenticate_incorrect(existent, mocked_girder_user, user_factory):
    if existent:
        # Don't set a password here, we'll expect it to be changed
        user_factory(email=mocked_girder_user['email'])

    authenticated_user = GirderBackend().authenticate(
        None, mocked_girder_user['email'], 'wrongpassword'
    )

    assert authenticated_user is None


@pytest.mark.django_db
def test_authenticate_not_found(mocker):
    mocker.patch.object(Profile, 'fetch_girder_user', return_value=None)

    authenticated_user = GirderBackend().authenticate(None, 'foo@bar.test', 'testpassword')

    assert authenticated_user is None
