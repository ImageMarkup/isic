import base64
import urllib.parse

from django.urls import reverse
import pytest


@pytest.mark.parametrize(
    'query_string',
    [
        {
            'sso': base64.b64encode(b'fake').decode(),
            'sig': 'fake',
        },
        {},
    ],
    ids=['bad_credentials', 'no_credentials'],
)
def test_sso_login_get(client, query_string):
    resp = client.get(reverse('discourse-sso-login'), data=query_string)

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
