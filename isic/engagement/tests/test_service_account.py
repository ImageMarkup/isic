from django.urls import reverse
from oauth2_provider.models import get_application_model
import pytest


def post_list(client, filters: dict | None = None, **kwargs):
    return client.post(
        reverse("api:engagement_accession_list"),
        filters or {},
        content_type="application/json",
        **kwargs,
    )


@pytest.fixture
def engagement_accessions(engagement_accession_factory, accession_factory):
    """Engagement accessions from two unrelated contributors, plus one that isn't engagement's."""
    return {
        "engagement": [engagement_accession_factory(), engagement_accession_factory()],
        "other": accession_factory(),
    }


@pytest.mark.django_db
def test_engagement_service_account_scope(
    client, engagement_service_app, client_credentials_token, engagement_accessions
):
    token = client_credentials_token(engagement_service_app)
    headers = {"Authorization": f"Bearer {token}"}
    engagement_accession = engagement_accessions["engagement"][0]

    resp = post_list(client, headers=headers)

    assert resp.status_code == 200, resp.json()
    # every engagement accession, regardless of who uploaded it or which contributor owns the
    # cohort, and nothing else.
    assert {result["id"] for result in resp.json()["results"]} == {
        engagement.accession_id for engagement in engagement_accessions["engagement"]
    }

    resp = client.get(
        reverse("api:engagement_accession_detail", args=[engagement_accession.external_id]),
        headers=headers,
    )
    assert resp.status_code == 200, resp.json()
    assert resp.json()["id"] == engagement_accession.accession_id


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("url_name", "wrong_application", "unset_setting"),
    [
        ("api:engagement_accession_list", True, False),
        ("api:engagement_accession_list", False, True),
        ("api:engagement_profile", False, False),
    ],
    ids=["another-application", "setting-unset", "userless-token-elsewhere"],
)
@pytest.mark.usefixtures("engagement_accessions")
def test_engagement_service_account_rejections(
    client,
    settings,
    engagement_service_app,
    client_credentials_token,
    oauth_app_factory,
    url_name,
    wrong_application,
    unset_setting,
):
    application = engagement_service_app
    if wrong_application:
        application = oauth_app_factory(
            "Other service", get_application_model().GRANT_CLIENT_CREDENTIALS
        )

    token = client_credentials_token(application)

    if unset_setting:
        settings.ISIC_ENGAGEMENT_SERVICE_OAUTH_CLIENT_ID = None

    headers = {"Authorization": f"Bearer {token}"}
    resp = (
        post_list(client, headers=headers)
        if url_name == "api:engagement_accession_list"
        else client.get(reverse(url_name), headers=headers)
    )

    # a client credentials token has no user, so anywhere it isn't explicitly recognized it's
    # anonymous rather than a server error.
    assert resp.status_code == 401, resp.json()
