import urllib.parse

from django.urls import reverse
import pytest

from isic.login.models import Profile


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
def test_sso_login_post(mocker, client, girder_user_factory, discourse_sso_credentials):
    girder_user = girder_user_factory(email='foo@bar.test', raw_password='testpassword')
    mocker.patch.object(Profile, 'fetch_girder_user', return_value=girder_user)

    resp = client.post(
        reverse('discourse-sso-login') + f'?{urllib.parse.urlencode(discourse_sso_credentials)}',
        {'username': 'foo@bar.test', 'password': 'testpassword'},
    )
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')
