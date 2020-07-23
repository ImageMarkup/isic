import urllib.parse

from django.urls import reverse
import pytest


@pytest.mark.parametrize(
    'login_url',
    [
        reverse('discourse-sso-login') + '?sso=ZmFrZQo=&sig=fake',  # 'fake' in base64
        reverse('discourse-sso-login'),
    ],
    ids=['bad_credentials', 'no_credentials'],
)
def test_sso_login_get(client, login_url):
    resp = client.get(login_url)

    assert resp.status_code == 302
    assert resp['Location'] == 'https://forum.isic-archive.com'


@pytest.mark.django_db
def test_sso_login_post(settings, client, user_factory, discourse_sso_credentials):
    # We don't want to actually test the GirderBackend here, and usage requires additional mocking
    settings.AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend']
    user = user_factory(raw_password='testpassword')

    resp = client.post(
        reverse('discourse-sso-login') + f'?{urllib.parse.urlencode(discourse_sso_credentials)}',
        {'username': user.email, 'password': 'testpassword'},
    )

    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')
