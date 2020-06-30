import pytest
import urllib
import base64
import hmac
import hashlib

from isic.discourse_sso.forms import DiscourseSSOLoginForm
from django.urls import reverse


def test_sso_login_get(client, girder_user):
    resp = client.get(reverse('discourse-sso-login'))
    assert resp.status_code == 302
    assert resp['Location'] == 'https://forum.isic-archive.com'

    # test bad SSO credentials
    resp = client.get(reverse('discourse-sso-login') + '?sso=fake&sig=fake')
    assert resp.status_code == 302
    assert resp['Location'] == 'https://forum.isic-archive.com'


def test_sso_login_post(client, girder_user, discourse_sso_credentials, monkeypatch):
    def _get_girder_user(*args, **kwargs):
        return girder_user

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user', _get_girder_user)

    def _get_girder_user_groups(*args, **kwargs):
        return []

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user_groups', _get_girder_user_groups)

    sso, sig = discourse_sso_credentials
    resp = client.post(
        reverse('discourse-sso-login') + f'?sso={sso}&sig={sig}',
        {'login': 'some-login', 'password': 'foo'},
    )
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://a-return-url.com/session/sso_login')
