from dataclasses import dataclass

from django.conf import settings
from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from isic.discourse_sso.forms import DiscourseSSOLoginForm
import hmac
import hashlib
import base64
import urllib
from django.http import JsonResponse

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
        key=settings.DISCOURSE_SSO_SECRET.encode('utf-8'),
        msg=sso,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if sig != expected_signature:
        # TODO: log forged sso
        raise Exception('Invalid SSO parameters.')

    return SSOParamSet(sso, sig, nonce, return_url)


def discourse_sso_login(request):
    try:
        sso_params = _get_sso_parameters(request)
    except Exception:
        return redirect('https://forum.isic-archive.com')

    if request.method == 'POST':
        form = DiscourseSSOLoginForm(request.POST)

        if form.is_valid():
            payload = {
                'nonce': sso_params.nonce,
                'email': form.girder_user['email'],
                'external_id': str(form.girder_user['_id']),
                'username': form.girder_user['login'],
                'name': '%s %s' % (form.girder_user['firstName'], form.girder_user['lastName']),
                'require_activation': 'false' if form.girder_user['emailVerified'] else 'true',
                'admin': 'true' if form.girder_user['admin'] else 'false',
                # Note, this list matches Discourse groups' "name" (which may only include numbers,
                # letters and underscores), not "Full Name" (which is human readable), so it may be of
                # limited utility
                'add_groups': ','.join(group['name'] for group in form.girder_user_groups),
            }
            payload = urllib.parse.urlencode(payload)
            payload = payload.encode('utf-8')
            payload = base64.b64encode(payload)

            digest = hmac.new(
                key=settings.DISCOURSE_SSO_SECRET.encode('utf-8'), msg=payload, digestmod=hashlib.sha256
            ).hexdigest()
            args = urllib.parse.urlencode({'sso': payload, 'sig': digest})

            return redirect(f'{sso_params.return_url}?{args}')
    else:
        form = DiscourseSSOLoginForm()

    return render(request, 'login.html', {'form': form})

