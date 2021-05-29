import urllib.parse

from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_sso_view_authenticated_success(authenticated_client, discourse_sso_credentials):
    resp = authenticated_client.get(reverse('discourse-sso-login'), data=discourse_sso_credentials)

    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')


@pytest.mark.django_db
def test_sso_view_authenticated_failure(
    settings, authenticated_client, bad_discourse_sso_credentials
):
    resp = authenticated_client.get(
        reverse('discourse-sso-login'), data=bad_discourse_sso_credentials
    )

    assert resp.status_code == 302
    assert resp['Location'].startswith(settings.ISIC_DISCOURSE_SSO_FAIL_URL)


@pytest.mark.django_db
def test_sso_view_get(client, discourse_sso_credentials):
    """Ensure the view works normally on GET."""
    resp = client.get(reverse('discourse-sso-login'), data=discourse_sso_credentials)

    assert resp.status_code == 200
    assert 'form' in resp.context_data
    assert not resp.context_data['form'].errors


@pytest.mark.django_db
def test_sso_view_post_success(client, discourse_sso_credentials, valid_user):
    resp = client.post(
        f'{reverse("discourse-sso-login")}?{urllib.parse.urlencode(discourse_sso_credentials)}',
        {'login': valid_user.email, 'password': 'testpassword'},
    )

    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')


@pytest.mark.django_db
def test_sso_view_post_failure_user(client, discourse_sso_credentials, invalid_user):
    resp = client.post(
        f'{reverse("discourse-sso-login")}?{urllib.parse.urlencode(discourse_sso_credentials)}',
        {'login': invalid_user.email, 'password': 'testpassword'},
    )

    assert resp.status_code == 302
    assert resp['Location'] == '/accounts/confirm-email/'


@pytest.mark.django_db
def test_sso_view_post_failure_credentials(client, bad_discourse_sso_credentials, valid_user):
    resp = client.post(
        f'{reverse("discourse-sso-login")}?{urllib.parse.urlencode(bad_discourse_sso_credentials)}',
        {'login': valid_user.email, 'password': 'testpassword'},
    )

    assert resp.status_code == 302
    assert resp['Location'] == 'https://forum.isic-archive.com'
