from datetime import timedelta

from django.test import RequestFactory, override_settings
from django.urls import path, reverse
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
        return {"anonymous": request.user.is_anonymous}

    @api.get("/is-authenticated", auth=auth.is_authenticated)
    def is_authenticated_view(request):
        return {}

    @api.get("/is-staff", auth=auth.is_staff)
    def is_staff_view(request):
        return {}

    @api.get(
        "/is-engagement-service",
        auth=auth.is_application("ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID"),
    )
    def is_application_view(request):
        return {"application": request.auth.application.name}

    urlpattern = path("test-oauth/", api.urls)

    from isic.urls import urlpatterns

    urlpatterns.append(urlpattern)

    yield

    urlpatterns.remove(urlpattern)
    NinjaAPI._registry.remove(request.function.__name__)


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


@pytest.fixture
def client_credentials_app_factory(user_factory, faker):
    def f():
        # the registrant is staff to prove the client doesn't inherit their access; registering
        # an application says nothing about what its tokens may do.
        return IsicOAuthApplication.objects.create(
            name=faker.company(),
            user=user_factory(is_staff=True),
            client_type=IsicOAuthApplication.CLIENT_CONFIDENTIAL,
            authorization_grant_type=IsicOAuthApplication.GRANT_CLIENT_CREDENTIALS,
        )

    return f


@pytest.fixture
def client_credentials_app(client_credentials_app_factory):
    return client_credentials_app_factory()


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_client_credentials_grant(client, client_credentials_app):
    app = client_credentials_app

    response = client.post(
        reverse("oauth2_provider:token"),
        {
            "grant_type": "client_credentials",
            "client_id": app.client_id,
            "client_secret": app.client_secret,
        },
    )
    assert response.status_code == 200, response.content
    token = response.json()["access_token"]

    access_token = get_access_token_model().objects.get(token=token)
    assert access_token.user is None
    assert access_token.application == app

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/test-oauth/allow-any", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"anonymous": True}
    assert client.get("/test-oauth/is-authenticated", headers=headers).status_code == 401
    assert client.get("/test-oauth/is-staff", headers=headers).status_code == 401


@pytest.mark.django_db
@pytest.mark.usefixtures("test_oauth_api_endpoints")
def test_application_restricted_endpoint(
    client, client_credentials_app_factory, nonstaff_user, user_factory, faker
):
    def get_token(app):
        response = client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "client_credentials",
                "client_id": app.client_id,
                "client_secret": app.client_secret,
            },
        )
        assert response.status_code == 200, response.content
        return response.json()["access_token"]

    url = "/test-oauth/is-engagement-service"
    app = client_credentials_app_factory()
    other_app = client_credentials_app_factory()
    token = get_token(app)

    assert client.get(url).status_code == 401
    # the endpoint names an application that isn't configured yet, so it accepts nothing
    assert client.get(url, headers={"Authorization": f"Bearer {token}"}).status_code == 401

    with override_settings(ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID=app.client_id):
        response = client.get(url, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json() == {"application": app.name}

        # a token issued to a different application is rejected
        other_token = get_token(other_app)
        response = client.get(url, headers={"Authorization": f"Bearer {other_token}"})
        assert response.status_code == 401

        # a user's token for the configured application is rejected, since only a client
        # credentials token represents the client itself
        user_token = get_access_token_model().objects.create(
            user=nonstaff_user,
            expires=timezone.now() + timedelta(seconds=300),
            token=faker.pystr(),
            application=app,
            scope="identity",
        )
        response = client.get(url, headers={"Authorization": f"Bearer {user_token.token}"})
        assert response.status_code == 401

        # a userless token issued to no application is rejected, since there's no client to
        # authorize
        applicationless_token = get_access_token_model().objects.create(
            user=None,
            expires=timezone.now() + timedelta(seconds=300),
            token=faker.pystr(),
            application=None,
        )
        response = client.get(
            url, headers={"Authorization": f"Bearer {applicationless_token.token}"}
        )
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
