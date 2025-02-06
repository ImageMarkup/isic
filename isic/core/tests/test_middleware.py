from datetime import timedelta

from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model
import pytest


@pytest.fixture
def oauth_app(user_factory):
    user = user_factory()
    return get_application_model().objects.create(
        name="Test Application",
        redirect_uris="http://localhost",
        user=user,
        client_type=get_application_model().CLIENT_CONFIDENTIAL,
        authorization_grant_type=get_application_model().GRANT_AUTHORIZATION_CODE,
    )


@pytest.fixture
def oauth_token_factory(oauth_app):
    def f(user):
        return get_access_token_model().objects.create(
            user=user,
            expires=timezone.now() + timedelta(seconds=300),
            token="some-token",
            application=oauth_app,
        )

    return f
