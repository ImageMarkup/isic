from django.contrib.auth.models import User
import pytest

from isic.login.girder import GirderBackend
from isic.login.models import Profile


@pytest.mark.django_db
@pytest.mark.parametrize('existent', [False, True], ids=['nonexistent', 'existent'])
@pytest.mark.parametrize(
    'correct_password', [False, True], ids=['incorrect_password', 'correct_password']
)
def test_authenticate(existent, correct_password, mocker, girder_user_factory, user_factory):
    girder_user = girder_user_factory(email='foo@bar.test', raw_password='testpassword')
    mocker.patch.object(Profile, 'fetch_girder_user', return_value=girder_user)

    if existent:
        # Don't set a password here, we'll expect it to be changed
        user = user_factory(email='foo@bar.test')

    set_password_spy = mocker.spy(User, 'set_password')

    authenticated_user = GirderBackend().authenticate(
        None, 'foo@bar.test', 'testpassword' if correct_password else 'wrongpassword'
    )

    if correct_password:
        assert authenticated_user
        assert authenticated_user.email == 'foo@bar.test'

        set_password_spy.assert_called_once()
        assert authenticated_user.check_password('testpassword')

        if existent:
            authenticated_user.id = user.id
    else:
        assert authenticated_user is None


@pytest.mark.django_db
def test_authenticate_not_found(mocker):
    mocker.patch.object(Profile, 'fetch_girder_user', return_value=None)

    authenticated_user = GirderBackend().authenticate(None, 'foo@bar.test', 'testpassword')

    assert authenticated_user is None
