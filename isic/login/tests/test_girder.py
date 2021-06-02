from django.contrib.auth.models import User
import pytest

from isic.login.backends import GirderBackend


@pytest.mark.django_db
@pytest.mark.parametrize('existent', [False, True], ids=['nonexistent', 'existent'])
def test_authenticate_correct(existent, mocker, mocked_girder_user, user_factory):
    if existent:
        # Don't set a password here, we'll expect it to be changed
        user = user_factory(
            email=mocked_girder_user['email'],
            password=f'bcrypt_girder${mocked_girder_user["salt"]}',
        )
    set_password_spy = mocker.spy(User, 'set_password')

    authenticated_user = GirderBackend().authenticate(
        None, email=mocked_girder_user['email'], password='testpassword'
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
        None, email=mocked_girder_user['email'], password='wrongpassword'
    )

    assert authenticated_user is None


@pytest.mark.django_db
def test_authenticate_disabled(disabled_girder_user):
    authenticated_user = GirderBackend().authenticate(
        None, email=disabled_girder_user['email'], password='testpassword'
    )

    assert authenticated_user is None


@pytest.mark.django_db
def test_authenticate_passwordless(passwordless_girder_user):
    authenticated_user = GirderBackend().authenticate(
        None, email=passwordless_girder_user['email'], password='testpassword'
    )

    assert authenticated_user is None


@pytest.mark.django_db
def test_authenticate_missing(missing_girder_user):
    authenticated_user = GirderBackend().authenticate(
        None, email=missing_girder_user['email'], password='testpassword'
    )

    assert authenticated_user is None
