import base64
from dataclasses import dataclass
import hashlib
import hmac
import urllib.parse

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest


@dataclass
class SSOParamSet:
    sso: bytes
    sig: str
    nonce: str
    return_url: str


class SSOException(Exception):
    pass


def _get_sso_parameters(request: HttpRequest) -> SSOParamSet:
    sso = request.GET.get('sso')
    sig = request.GET.get('sig')

    if not sig or not sso:
        raise SSOException('Invalid SSO parameters.')

    sso = sso.encode('utf-8')

    # Extract nonce and return URL
    qs = base64.b64decode(sso)
    qs = qs.decode('utf-8')
    parsed = urllib.parse.parse_qs(qs)

    if 'nonce' not in parsed or 'return_sso_url' not in parsed:
        raise SSOException('Invalid SSO parameters.')
    else:
        nonce = parsed['nonce'][0]
        return_url = parsed['return_sso_url'][0]

    # Ensure HMAC-SHA256 digest matches provided signature
    expected_signature = hmac.new(
        key=settings.ISIC_DISCOURSE_SSO_SECRET.encode('utf-8'),
        msg=sso,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if sig != expected_signature:
        # TODO: log forged sso
        raise SSOException('Invalid SSO parameters.')

    return SSOParamSet(sso, sig, nonce, return_url)


def _get_sso_redirect_url(user: User, sso_params: SSOParamSet) -> str:
    payload = {
        'nonce': sso_params.nonce,
        'email': user.email,
        'external_id': user.profile.girder_id,
        'username': user.username,
        'name': f'{user.first_name} {user.last_name}',
        'require_activation': 'false' if user.profile.email_verified else 'true',
        'admin': 'true' if user.is_superuser else 'false',
    }
    payload = urllib.parse.urlencode(payload)
    payload = payload.encode('utf-8')
    payload = base64.b64encode(payload)

    digest = hmac.new(
        key=settings.ISIC_DISCOURSE_SSO_SECRET.encode('utf-8'),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    args = urllib.parse.urlencode({'sso': payload, 'sig': digest})

    return f'{sso_params.return_url}?{args}'
