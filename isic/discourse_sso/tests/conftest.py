import base64
import hashlib
import hmac
import urllib.parse

from django.conf import settings
import pytest


@pytest.fixture
def discourse_sso_credentials():
    # returns a discourse sso payload, and a signature
    sso_payload = {
        'nonce': 'some-fake-nonce',
        'return_sso_url': 'https://a-return-url.com/session/sso_login',
    }
    sso_payload = urllib.parse.urlencode(sso_payload).encode('utf-8')
    sso_payload = base64.b64encode(sso_payload)
    signature = hmac.new(
        key=settings.ISIC_DISCOURSE_SSO_SECRET.encode('utf-8'),
        msg=sso_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {'sso': sso_payload.decode('utf-8'), 'sig': signature}
