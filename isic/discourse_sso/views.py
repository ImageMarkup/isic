import base64
from dataclasses import dataclass
import hashlib
import hmac
from typing import Dict
import urllib

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from isic.login.girder import get_girder_user, get_girder_user_groups


@dataclass
class SSOParamSet:
    sso: bytes
    sig: str
    nonce: str
    return_url: str


def _get_sso_parameters(request) -> SSOParamSet:
    sso = request.GET.get('sso')
    sig = request.GET.get('sig')

    if not sig or not sso:
        raise Exception('Invalid SSO parameters.')

    # breakpoint()
    sso = sso.encode('utf-8')

    # Extract nonce and return URL
    qs = base64.b64decode(sso)
    qs = qs.decode('utf-8')
    parsed = urllib.parse.parse_qs(qs)

    if 'nonce' not in parsed or 'return_sso_url' not in parsed:
        raise Exception('Invalid SSO parameters.')
    else:
        nonce = parsed['nonce'][0]
        return_url = parsed['return_sso_url'][0]

    # Ensure HMAC-SHA256 digest matches provided signature
    expected_signature = hmac.new(
        key=settings.DISCOURSE_SSO_SECRET.encode('utf-8'), msg=sso, digestmod=hashlib.sha256,
    ).hexdigest()
    if sig != expected_signature:
        # TODO: log forged sso
        raise Exception('Invalid SSO parameters.')

    return SSOParamSet(sso, sig, nonce, return_url)


def _get_redirect_url(girder_user: Dict, sso_params: Dict) -> str:
    payload = {
        'nonce': sso_params.nonce,
        'email': girder_user['email'],
        'external_id': str(girder_user['_id']),
        'username': girder_user['login'],
        'name': '%s %s' % (girder_user['firstName'], girder_user['lastName']),
        'require_activation': 'false' if girder_user['emailVerified'] else 'true',
        'admin': 'true' if girder_user['admin'] else 'false',
        # Note, this list matches Discourse groups' "name" (which may only include numbers,
        # letters and underscores), not "Full Name" (which is human readable), so it
        # may be of limited utility
        'add_groups': ','.join(group['name'] for group in get_girder_user_groups(girder_user)),
    }
    payload = urllib.parse.urlencode(payload)
    payload = payload.encode('utf-8')
    payload = base64.b64encode(payload)

    digest = hmac.new(
        key=settings.DISCOURSE_SSO_SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256,
    ).hexdigest()
    args = urllib.parse.urlencode({'sso': payload, 'sig': digest})

    return f'{sso_params.return_url}?{args}'


def discourse_sso_login(request):
    try:
        sso_params = _get_sso_parameters(request)
    except Exception:
        return redirect('https://forum.isic-archive.com')

    if request.user.is_authenticated:
        return redirect(_get_redirect_url(get_girder_user(request.user.email), sso_params))
    elif request.method == 'POST':
        # Note: unlike other django forms, the first argument is not data, see:
        # https://stackoverflow.com/a/21504550
        form = AuthenticationForm(data=request.POST)

        if form.is_valid():
            login(request, form.get_user())
            return redirect(
                _get_redirect_url(get_girder_user(form.cleaned_data['username']), sso_params)
            )
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})
