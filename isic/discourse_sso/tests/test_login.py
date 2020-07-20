import urllib

from django.urls import reverse
import pytest

from isic.discourse_sso import views

@pytest.mark.parametrize(
    'login_url',
    [
        reverse('discourse-sso-login') + '?sso=ZmFrZQo=&sig=fake',  # 'fake' in base64
        reverse('discourse-sso-login'),
    ],
    ids=['bad_credentials', 'no_credentials'],
)
def test_sso_login_get(client, girder_user, login_url):
    resp = client.get(login_url)
    assert resp.status_code == 302
    assert resp['Location'] == 'https://forum.isic-archive.com'


def test_sso_login_post(client, girder_user, discourse_sso_credentials, monkeypatch):
    def _get_girder_user(*args, **kwargs):
        return girder_user

    monkeypatch.setattr(views, 'get_girder_user', _get_girder_user)

    def _get_girder_user_groups(*args, **kwargs):
        return []

    monkeypatch.setattr(views, 'get_girder_user_groups', _get_girder_user_groups)

    resp = client.post(
        reverse('discourse-sso-login') + f'?{urllib.parse.urlencode(discourse_sso_credentials)}',
        {'login': 'some-login', 'password': 'foo'},
    )
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')
