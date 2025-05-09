from oauth2_provider.models import get_application_model
import pytest

from isic.core.models.base import IsicOAuthApplication


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
