import pytest
from pytest_factoryboy import register
from rest_framework.test import APIClient

from .factories import ProfileFactory, UserFactory


# Can't use the register decorators with circular factory references
register(ProfileFactory)
register(UserFactory)


@pytest.fixture
def api_client():
    return APIClient()
