from collections.abc import Callable

from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.operation import PathView
from ninja.security import HttpBearer, SessionAuth
from ninja.utils import check_csrf
from oauth2_provider.oauth2_backends import get_oauthlib_core

from isic.core.permissions import SessionAuthStaffUser

ACCESS_PERMS = ["any", "is_authenticated", "is_staff"]


class CsrfFixedSessionAuth(SessionAuth):
    def _get_key(self, request: HttpRequest) -> str | None:
        if self.csrf:
            # Work around https://github.com/vitalik/django-ninja/issues/1068
            # Maybe related https://github.com/vitalik/django-ninja/issues/1101
            path_view: PathView = request.resolver_match.func.__self__
            view_func = path_view._find_operation(request).view_func
            # The upstream implementation doesn't send "view_func" to "check_csrf", so a
            # "csrf_exempt" annotation can't be detected.
            error_response = check_csrf(request, view_func)
            if error_response:
                raise HttpError(403, "CSRF check Failed")
        return request.COOKIES.get(self.param_name)


django_auth = CsrfFixedSessionAuth()


class OAuth2AuthBearer(HttpBearer):
    def __init__(self, perm: str):
        if perm not in ACCESS_PERMS:
            raise ValueError(f"Invalid permission: {perm}")
        self.perm = perm
        super().__init__()

    # This is a reimplementation of the django-oauth-toolkit authentication backend for DRF.
    # See https://github.com/jazzband/django-oauth-toolkit/blob/a4ae1d4716bcabe45d80a787f4064022f11e584f/oauth2_provider/contrib/rest_framework/authentication.py#L8  # noqa: E501
    def authenticate(self, request, token):
        oauthlib_core = get_oauthlib_core()
        valid, r = oauthlib_core.verify_request(request, scopes=[])

        if valid:
            # See https://github.com/vitalik/django-ninja/issues/76 for why we have to manually set
            # request.user here.
            request.user = r.user

            if self.perm == "any":
                return r.user, token
            if self.perm == "is_authenticated" and r.user.is_authenticated:
                return r.user, token
            if self.perm == "is_staff" and r.user.is_authenticated and r.user.is_staff:
                return r.user, token
        elif self.perm == "any":
            return True
        else:
            request.oauth2_error = getattr(r, "oauth2_error", {})


# Always test OAuth2 before session auth, since OAuth2 doesn't have CSRF messiness.
# The lambda _: True is to handle the case where a user doesn't pass any authentication.
allow_any: list[Callable] = [OAuth2AuthBearer("any"), lambda _: True, django_auth]
is_authenticated = [OAuth2AuthBearer("is_authenticated"), django_auth]
is_staff = [OAuth2AuthBearer("is_staff"), SessionAuthStaffUser()]
