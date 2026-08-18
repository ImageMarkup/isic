from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from ninja.security import HttpBearer, django_auth
from oauth2_provider.oauth2_backends import get_oauthlib_core

from isic.core.permissions import SessionAuthStaffUser

ACCESS_PERMS = ["any", "is_authenticated", "is_staff"]


class OAuth2AuthBearer(HttpBearer):
    def __init__(self, perm: str):
        if perm not in ACCESS_PERMS:
            raise ValueError(f"Invalid permission: {perm}")
        self.perm = perm
        super().__init__()

    # This is a reimplementation of the django-oauth-toolkit authentication backend for DRF.
    # See https://github.com/jazzband/django-oauth-toolkit/blob/a4ae1d4716bcabe45d80a787f4064022f11e584f/oauth2_provider/contrib/rest_framework/authentication.py#L8  # noqa: E501
    def authenticate(self, request, token) -> Any | None:
        oauthlib_core = get_oauthlib_core()
        valid, r = oauthlib_core.verify_request(request, scopes=[])

        if valid:
            # client credentials tokens have no user, since the client authenticates as itself
            # rather than on behalf of a resource owner. such a token gets no more access than
            # an anonymous caller until endpoints authorize the application itself.
            user = r.user or AnonymousUser()

            # See https://github.com/vitalik/django-ninja/issues/76 for why we have to manually set
            # request.user here.
            request.user = user

            if self.perm == "any":
                return user, token
            if self.perm == "is_authenticated" and user.is_authenticated:
                return user, token
            if self.perm == "is_staff" and user.is_authenticated and user.is_staff:
                return user, token
        elif self.perm == "any":
            return True
        else:
            request.oauth2_error = getattr(r, "oauth2_error", {})

        return None


class OAuth2ApplicationBearer(HttpBearer):
    """
    Require a token issued to one of the OAuth applications named by the given settings.

    Client credentials tokens have no user, so the application a token was issued to is the
    only principal an endpoint can authorize. The settings are read per request, so an unset
    client_id rejects every token rather than accepting any.
    """

    def __init__(self, *client_id_settings: str):
        if not client_id_settings:
            raise ValueError("At least one client_id setting is required.")

        self.client_id_settings = client_id_settings
        super().__init__()

    def authenticate(self, request, token) -> Any | None:
        oauthlib_core = get_oauthlib_core()
        valid, r = oauthlib_core.verify_request(request, scopes=[])

        if not valid:
            request.oauth2_error = getattr(r, "oauth2_error", {})
            return None

        # only client credentials tokens have no user. Requiring that here means a user's
        # token for the same application, which represents that user rather than the client
        # itself, can't reach an endpoint meant for the client.
        if r.access_token.user_id is not None:
            return None

        # the application is nullable, and a token issued to no application has no client to
        # authorize.
        if r.access_token.application_id is None:
            return None

        allowed_client_ids = {
            client_id
            for client_id in (getattr(settings, name, None) for name in self.client_id_settings)
            if client_id
        }

        if r.access_token.application.client_id not in allowed_client_ids:
            return None

        request.user = AnonymousUser()

        # returning the access token makes it available to the endpoint as request.auth, which
        # carries the application the token was issued to.
        return r.access_token


def is_application(*client_id_settings: str) -> list[Callable]:
    return [OAuth2ApplicationBearer(*client_id_settings)]


# The lambda _: True is to handle the case where a user doesn't pass any authentication.
allow_any: list[Callable] = [django_auth, OAuth2AuthBearer("any"), lambda _: True]
is_authenticated = [django_auth, OAuth2AuthBearer("is_authenticated")]
is_staff = [SessionAuthStaffUser(), OAuth2AuthBearer("is_staff")]
