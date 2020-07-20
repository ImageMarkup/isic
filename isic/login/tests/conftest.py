import base64
import hashlib
import hmac
import urllib

from bson.objectid import ObjectId
import pytest

from isic.discourse_sso import views


@pytest.fixture
def discourse_sso_secret(monkeypatch):
    monkeypatch.setattr(views.settings, 'DISCOURSE_SSO_SECRET', 'a-fake-discourse-sso-secret')
    return 'a-fake-discourse-sso-secret'


@pytest.fixture
def discourse_sso_credentials(discourse_sso_secret):
    # returns a discourse sso payload, and a signature
    sso_payload = {
        'nonce': 'some-fake-nonce',
        'return_sso_url': 'https://a-return-url.com/session/sso_login',
    }
    sso_payload = urllib.parse.urlencode(sso_payload).encode('utf-8')
    sso_payload = base64.b64encode(sso_payload)
    signature = hmac.new(
        key=discourse_sso_secret.encode('utf-8'), msg=sso_payload, digestmod=hashlib.sha256
    ).hexdigest()
    return {'sso': sso_payload.decode('utf-8'), 'sig': signature}


@pytest.fixture
def girder_user():
    return {
        '_id': ObjectId(),
        'login': 'some-login',
        'email': 'a-fake-email@email.test',
        'firstName': '',
        'lastName': '',
        'emailVerified': True,
        'admin': True,
        'salt': '$2b$12$kUO9gFgY1NDYI9/rf1GWVe1RgOpbtLeiap/SZMv6ByVSsbG.sjQni',  # foo
    }
