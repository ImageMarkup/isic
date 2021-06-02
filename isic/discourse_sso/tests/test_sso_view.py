from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_sso_view_authenticated_success(authenticated_client, discourse_sso_credentials):
    resp = authenticated_client.get(reverse('discourse-sso'), data=discourse_sso_credentials)

    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')


@pytest.mark.django_db
def test_sso_view_authenticated_failure(
    settings, authenticated_client, bad_discourse_sso_credentials
):
    resp = authenticated_client.get(reverse('discourse-sso'), data=bad_discourse_sso_credentials)

    assert resp.status_code == 302
    assert resp['Location'].startswith(settings.ISIC_DISCOURSE_SSO_FAIL_URL)


@pytest.mark.django_db
def test_sso_view_unauthenticated(client, discourse_sso_credentials):
    resp = client.get(reverse('discourse-sso'), data=discourse_sso_credentials)

    assert resp.status_code == 302
    assert resp['Location'].startswith(reverse('account_login'))
