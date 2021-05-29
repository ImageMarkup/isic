from allauth.account.views import LoginView
from django.conf import settings
from django.http.response import HttpResponseRedirectBase
from django.shortcuts import redirect

from isic.discourse_sso.utils import SSOException, _get_sso_parameters, _get_sso_redirect_url


class DiscourseSsoLoginView(LoginView):
    def _get_sso_redirect_url(self):
        try:
            sso_params = _get_sso_parameters(self.request)
        except SSOException:
            return settings.ISIC_DISCOURSE_SSO_FAIL_URL

        return _get_sso_redirect_url(self.request.user, sso_params)

    def get_authenticated_redirect_url(self):
        # Called when the user is already authenticated
        return self._get_sso_redirect_url()

    def get_success_url(self):
        # Called when a form submission was successful, but before the user is actually logged in.
        # The real redirect URL can't be known now, since it requires the user to construct.
        # Return a sentinel value, so the login flow will proceed and construct a redirect to this
        # "location".
        # There are other reasons the login flow could fail and redirect to a different location
        # (e.g. email validation required).
        # Use ISIC_DISCOURSE_SSO_FAIL_URL as the sentinel in case something goes very wrong,
        # so the redirect should send the user somewhere sane.
        return settings.ISIC_DISCOURSE_SSO_FAIL_URL

    def form_valid(self, form):
        # Start the whole normal login flow
        response = super().form_valid(form)

        # Check if this made it through the login flow successfully and the response is primed
        # to redirect the user to the sentinel value.
        if (
            self.request.user.is_authenticated
            and isinstance(response, HttpResponseRedirectBase)
            and response.url == settings.ISIC_DISCOURSE_SSO_FAIL_URL
        ):
            # Validate SSO and redirect to the actual appropriate location
            response = redirect(self._get_sso_redirect_url(), permanent=False)

        return response
