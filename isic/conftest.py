from django.test.client import Client
import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from .factories import ProfileFactory, UserFactory


@pytest.fixture
def user_client(user_factory):
    u = user_factory()
    client = Client()
    client.force_login(u)
    return client


@pytest.fixture
def staff_user(user_factory):
    return user_factory(is_staff=True)


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def authenticated_api_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def staff_api_client(staff_user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


register(ProfileFactory)
register(UserFactory)
