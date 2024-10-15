from datetime import timedelta
import logging

from django.urls import reverse
from django.utils import timezone
from oauth2_provider.models import get_access_token_model, get_application_model
import pytest


@pytest.fixture()
def oauth_app(user_factory):
    user = user_factory()
    return get_application_model().objects.create(
        name="Test Application",
        redirect_uris="http://localhost",
        user=user,
        client_type=get_application_model().CLIENT_CONFIDENTIAL,
        authorization_grant_type=get_application_model().GRANT_AUTHORIZATION_CODE,
    )


@pytest.fixture()
def oauth_token_factory(oauth_app):
    def f(user):
        return get_access_token_model().objects.create(
            user=user,
            expires=timezone.now() + timedelta(seconds=300),
            token="some-token",
            application=oauth_app,
        )

    return f


@pytest.mark.django_db()
@pytest.mark.parametrize(("route"), ["api:user_me", "core/image-browser"], ids=["ninja", "django"])
def test_log_request_user_id(authenticated_client, user, caplog, route):
    with caplog.at_level(logging.INFO, logger="isic.middleware"):
        r = authenticated_client.get(reverse(route))
        assert r.status_code == 200
        assert f"user:{user.id}" in caplog.text, caplog.text


@pytest.mark.django_db()
def test_log_request_user_id_oauth(user, client, oauth_token_factory, caplog):
    token = oauth_token_factory(user)

    with caplog.at_level(logging.INFO, logger="isic.middleware"):
        r = client.get(
            reverse("api:user_me"),
            headers={"Authorization": f"Bearer {token.token}"},
        )
        assert r.status_code == 200
        assert f"user:{user.id}" in caplog.text, caplog.text
