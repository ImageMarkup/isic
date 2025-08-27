from base64 import b64encode
from datetime import timedelta
import secrets

from allauth.core import context
from allauth.idp.oidc.adapter import get_adapter
from allauth.idp.oidc.models import Client, Token
from django.test import RequestFactory
from django.urls import path
from django.utils import timezone
from ninja import NinjaAPI
import pytest

from isic import auth


@pytest.fixture
def oauth_app(user_factory):
    return Client.objects.create(
        name="Test Application",
        scopes="openid",
        type=Client.Type.PUBLIC,
        grant_types=Client.GrantType.DEVICE_CODE,
        redirect_uris="http://foo.com",
        response_types="code",
        skip_consent=False,
    )


@pytest.fixture
def oauth_token_factory(oauth_app):
    def f(user):
        token = secrets.token_hex(8)
        oauth_app.token_set.create(
            user=user,
            expires_at=timezone.now() + timedelta(seconds=300),
            hash=get_adapter().hash_token(token),
            type=Token.Type.ACCESS_TOKEN,
            scopes=["openid"],
        )
        return token

    return f


@pytest.mark.skip(reason="TODO: needs to be ported to allauth")
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
    pass


@pytest.fixture
def test_oauth_api_endpoints(request):
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
    return oauth_token_factory(user)


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


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_permissioned_token_auth_invalid_token():
    request = RequestFactory(
        headers={"Authorization": f"Bearer {b64encode(b'invalidtoken').decode()}"}
    ).get("/test-oauth/allow-any")

    token_auth = auth.PermissionedTokenAuth("any", scope=[])

    # allauth APIs assume a global request context, so we need to set it up manually
    with context.request_context(request):
        result = token_auth(request)
        assert result is True

        token_auth = auth.PermissionedTokenAuth("is_authenticated", scope=[])
        result = token_auth(request)
        assert result is False

        token_auth = auth.PermissionedTokenAuth("is_staff", scope=[])
        result = token_auth(request)
        assert result is False
