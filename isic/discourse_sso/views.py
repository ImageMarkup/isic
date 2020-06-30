from django.conf import settings
from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from isic.discourse_sso.forms import DiscourseSSOLoginForm
import hmac
import hashlib
import base64
import urllib
from django.http import JsonResponse


class DiscourseSSOLoginView(FormView):
    template_name = 'login.html'
    form_class = DiscourseSSOLoginForm

    sso = None
    sig = None
    nonce = None
    success_url = None

    def _setup_request(self, request):
        self.sso = request.GET.get('sso')
        self.sig = request.GET.get('sig')

        if not self.sig or not self.sso:
            return redirect('https://forum.isic-archive.com')

        self.sso = self.sso.encode('utf-8')

        # Extract nonce and return URL
        qs = base64.b64decode(self.sso)
        qs = qs.decode('utf-8')
        parsed = urllib.parse.parse_qs(qs)

        if 'nonce' not in parsed or 'return_sso_url' not in parsed:
            return redirect('https://forum.isic-archive.com')
        else:
            self.nonce = parsed['nonce'][0]
            self.success_url = parsed['return_sso_url'][0]

        # Ensure HMAC-SHA256 digest matches provided signature
        expected_signature = hmac.new(
            key=settings.DISCOURSE_SSO_SECRET.encode('utf-8'),
            msg=self.sso,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if self.sig != expected_signature:
            # TODO: log forged sso
            return redirect('https://forum.isic-archive.com')

    def get(self, request, *args, **kwargs):
        maybe_redirect = self._setup_request(request)

        if maybe_redirect:
            return maybe_redirect

        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        maybe_redirect = self._setup_request(request)

        if maybe_redirect:
            return maybe_redirect

        return super().post(request, *args, **kwargs)

    def form_valid(self, form: DiscourseSSOLoginForm):
        payload = {
            'nonce': self.nonce,
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

        return redirect(f'{self.success_url}?{args}')
