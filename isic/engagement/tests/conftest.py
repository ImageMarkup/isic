import base64
import hashlib
import secrets
from urllib.parse import parse_qs, urlparse

from django.urls import reverse
from oauth2_provider.models import get_application_model
import pytest

REDIRECT_URI = "http://localhost"


@pytest.fixture
def engagement_accessions_by_state(accessions_by_state, engagement_accession_factory):
    """One engagement platform accession in every state, all within a single cohort."""
    for accession in accessions_by_state.values():
        engagement_accession_factory(accession=accession)

    return accessions_by_state


@pytest.fixture
def oauth_app_factory(user_factory):
    def f(name: str, grant_type: str | None = None):
        application_model = get_application_model()
        return application_model.objects.create(
            name=name,
            redirect_uris=REDIRECT_URI,
            user=user_factory(),
            client_type=application_model.CLIENT_CONFIDENTIAL,
            authorization_grant_type=grant_type or application_model.GRANT_AUTHORIZATION_CODE,
        )

    return f


@pytest.fixture
def engagement_app(oauth_app_factory, settings):
    """Create the engagement platform's OAuth application and point the setting at it."""
    app = oauth_app_factory("Engagement Platform")
    settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID = app.client_id
    return app


@pytest.fixture
def engagement_service_app(oauth_app_factory, settings):
    """Create the engagement platform's machine to machine application."""
    app = oauth_app_factory(
        "Engagement Platform Service", get_application_model().GRANT_CLIENT_CREDENTIALS
    )
    settings.ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID = app.client_id
    return app


@pytest.fixture
def other_oauth_app(oauth_app_factory):
    return oauth_app_factory("Other app")


@pytest.fixture
def client_credentials_token(client):
    def f(application):
        response = client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "client_credentials",
                "client_id": application.client_id,
                "client_secret": application.client_secret,
            },
        )
        assert response.status_code == 200, response.content

        return response.json()["access_token"]

    return f


@pytest.fixture
def grant_token(client):
    def f(user, application):
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        authorize_params = {
            "response_type": "code",
            "client_id": application.client_id,
            "redirect_uri": REDIRECT_URI,
            "scope": "identity",
            "state": secrets.token_urlsafe(8),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        client.force_login(user)

        # Render the consent screen, then approve it, exactly as a user would.
        consent_response = client.get(reverse("oauth2_provider:authorize"), authorize_params)
        assert consent_response.status_code == 200, consent_response.content

        approval_response = client.post(
            reverse("oauth2_provider:authorize"), {**authorize_params, "allow": True}
        )
        assert approval_response.status_code == 302, approval_response.content
        code = parse_qs(urlparse(approval_response["Location"]).query)["code"][0]

        token_response = client.post(
            reverse("oauth2_provider:token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": application.client_id,
                "client_secret": application.client_secret,
                "code_verifier": code_verifier,
            },
        )
        assert token_response.status_code == 200, token_response.content

        return token_response.json()

    return f
