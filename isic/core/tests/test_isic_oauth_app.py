from datetime import timedelta

from django.test import RequestFactory
from django.urls import path
from django.utils import timezone
from ninja import NinjaAPI
from oauth2_provider.models import get_access_token_model, get_application_model
import pytest

from isic import auth
from isic.core.models.base import IsicOAuthApplication


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


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("uri", "allowed_uris", "allowed"),
    [
        ("http://foo.com", "http://foo.com", True),
        ("http://bar.com", "http://foo.com", False),
        ("http://bar.com", "http://foo.com ^http://bar.com$", True),
        ("http://bar5.com", "http://foo.com ^http://bar[0-9]\\.com$", True),
    ],
)
def test_redirect_uri_allowed(user, uri, allowed_uris, allowed):
    app = IsicOAuthApplication.objects.create(
        name="Test Application",
        redirect_uris=allowed_uris,
        user=user,
        client_type=get_application_model().CLIENT_CONFIDENTIAL,
        authorization_grant_type=get_application_model().GRANT_AUTHORIZATION_CODE,
    )

    assert app.redirect_uri_allowed(uri) == allowed


@pytest.fixture
def test_oauth_api_endpoints(request):
    # this is pretty gross, but DOT requires a "more" real request object be created, meaning the
    # ninja test client can't be used since it mocks it. using the django test client means we have
    # to add real routes and then remove them.
    api = NinjaAPI(urls_namespace=request.function.__name__, auth=auth.allow_any)

    @api.get("/allow-any")
    def allow_any_view(request):
        return {}

    @api.get("/is-authenticated", auth=auth.is_authenticated)
    def is_authenticated_view(request):
        return {}

    @api.get("/is-staff", auth=auth.is_staff)
    def is_staff_view(request):
        return {}

    urlpattern = path("test-oauth/", api.urls)

    from isic.urls import urlpatterns

    urlpatterns.append(urlpattern)

    yield

    urlpatterns.remove(urlpattern)


def get_bearer_token(user, oauth_token_factory):
    token = oauth_token_factory(user)
    return token.token


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_allow_any_with_no_auth(client):
    response = client.get("/test-oauth/allow-any")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_allow_any_with_session_auth(client, user):
    client.force_login(user)
    response = client.get("/test-oauth/allow-any")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_allow_any_with_bearer_token(client, user, oauth_token_factory):
    token = get_bearer_token(user, oauth_token_factory)
    response = client.get("/test-oauth/allow-any", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_authenticated_with_no_auth(client):
    response = client.get("/test-oauth/is-authenticated")
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_authenticated_with_session_auth(client, user):
    client.force_login(user)
    response = client.get("/test-oauth/is-authenticated")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_authenticated_with_bearer_token(client, user, oauth_token_factory):
    token = get_bearer_token(user, oauth_token_factory)
    response = client.get(
        "/test-oauth/is-authenticated", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_staff_with_no_auth(client):
    response = client.get("/test-oauth/is-staff")
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_staff_with_session_auth(client, staff_user):
    client.force_login(staff_user)
    response = client.get("/test-oauth/is-staff")
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_staff_with_bearer_token(client, staff_user, oauth_token_factory):
    token = get_bearer_token(staff_user, oauth_token_factory)
    response = client.get("/test-oauth/is-staff", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_staff_with_nonstaff_user_session(client, nonstaff_user):
    client.force_login(nonstaff_user)
    response = client.get("/test-oauth/is-staff")
    assert response.status_code == 401


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_is_staff_with_nonstaff_bearer_token(client, nonstaff_user, oauth_token_factory):
    token = get_bearer_token(nonstaff_user, oauth_token_factory)
    response = client.get("/test-oauth/is-staff", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_oauth2authbearer_any_accepts_invalid_token():
    bearer = auth.OAuth2AuthBearer("any")
    request = RequestFactory().get("/")
    result = bearer.authenticate(request, "invalidtoken")
    assert result is True

    bearer = auth.OAuth2AuthBearer("is_authenticated")
    result = bearer.authenticate(request, "invalidtoken")
    assert result is None

    bearer = auth.OAuth2AuthBearer("is_staff")
    result = bearer.authenticate(request, "invalidtoken")
    assert result is None
