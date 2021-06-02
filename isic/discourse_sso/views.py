from django.conf import settings
from django.urls import reverse
from django.utils.http import urlencode
from django.views.generic import RedirectView

from isic.discourse_sso.utils import SSOException, _get_sso_parameters, _get_sso_redirect_url


class DiscourseSsoRedirectView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if self.request.user.is_authenticated:
            try:
                sso_params = _get_sso_parameters(self.request)
            except SSOException:
                return settings.ISIC_DISCOURSE_SSO_FAIL_URL
            else:
                return _get_sso_redirect_url(self.request.user, sso_params)
        else:
            current_url = self.request.get_full_path()
            # Redirect to account_login, with a "next=" back to here
            return f'{reverse("account_login")}?{urlencode({"next": current_url})}'
