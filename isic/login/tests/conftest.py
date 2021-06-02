import pytest
from pytest_factoryboy import register

import isic.login.girder

from .factories import GirderUserFactory

register(GirderUserFactory, 'girder_user')


@pytest.fixture(autouse=True)
def enable_mongo_url(settings):
    # Setting this will enable GirderBackend
    settings.ISIC_MONGO_URI = 'mongodb://localhost:27017/girder'


@pytest.fixture
def mocked_girder_user(mocker, girder_user_factory):
    girder_user = girder_user_factory(raw_password='testpassword')
    mocker.patch.object(isic.login.girder, '_fetch_girder_user', return_value=girder_user)
    return girder_user


@pytest.fixture
def disabled_girder_user(mocker, girder_user_factory):
    girder_user = girder_user_factory(status='disabled', raw_password='testpassword')
    mocker.patch.object(isic.login.girder, '_fetch_girder_user', return_value=girder_user)
    return girder_user


@pytest.fixture
def passwordless_girder_user(mocker, girder_user_factory):
    girder_user = girder_user_factory(raw_password=None)
    mocker.patch.object(isic.login.girder, '_fetch_girder_user', return_value=girder_user)
    return girder_user


@pytest.fixture
def missing_girder_user(mocker, girder_user_factory):
    girder_user = girder_user_factory(raw_password='testpassword')
    mocker.patch.object(isic.login.girder, '_fetch_girder_user', return_value=None)
    return girder_user
