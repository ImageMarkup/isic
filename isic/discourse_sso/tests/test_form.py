import pytest
import urllib
import base64
import hmac
import hashlib

from isic.discourse_sso.forms import DiscourseSSOLoginForm


def test_sso_login_form(client, girder_user, monkeypatch):
    def _get_girder_user(*args, **kwargs):
        return girder_user

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user', _get_girder_user)

    def _get_girder_user_groups(*args, **kwargs):
        return []

    monkeypatch.setattr(DiscourseSSOLoginForm, '_get_girder_user_groups', _get_girder_user_groups)

    form = DiscourseSSOLoginForm(data={'login': 'a-username', 'password': 'foo'})
    assert form.is_valid(), form.errors
