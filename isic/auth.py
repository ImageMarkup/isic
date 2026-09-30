from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from oauth2_provider.contrib.rest_framework import authentication
from oauth2_provider.models import get_access_token_model
from rest_framework.exceptions import NotAuthenticated
from rest_framework.permissions import SAFE_METHODS, BasePermission


class OAuth2Authentication(authentication.OAuth2Authentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, access_token = result
        # client credentials tokens have no user, since the client authenticates as itself
        # rather than on behalf of a resource owner. such a token gets no more access than
        # an anonymous caller until endpoints authorize the application itself.
        return user or AnonymousUser(), access_token


# These raise NotAuthenticated rather than returning False because DRF answers a caller that
# authenticated but lacks access with a 403, and every failed access check in this API is a 401.


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view) -> bool:
        if not request.user.is_authenticated:
            raise NotAuthenticated
        return True


class IsStaff(BasePermission):
    def has_permission(self, request, view) -> bool:
        if not request.user.is_staff:
            raise NotAuthenticated
        return True


class ReadOnly(BasePermission):
    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS


def is_application(*client_id_settings: str) -> type[BasePermission]:
    """
    Require a token issued to one of the OAuth applications named by the given settings.

    Client credentials tokens have no user, so the application a token was issued to is the
    only principal an endpoint can authorize. The settings are read per request, so an unset
    client_id rejects every token rather than accepting any.
    """
    if not client_id_settings:
        raise ValueError("At least one client_id setting is required.")

    class IsApplication(BasePermission):
        def has_permission(self, request, view) -> bool:
            access_token = request.auth

            # only client credentials tokens have no user. Requiring that here means a user's
            # token for the same application, which represents that user rather than the client
            # itself, can't reach an endpoint meant for the client.
            # the application is nullable, and a token issued to no application has no client
            # to authorize.
            if (
                not isinstance(access_token, get_access_token_model())
                or access_token.user_id is not None
                or access_token.application_id is None
            ):
                raise NotAuthenticated

            allowed_client_ids = {
                client_id
                for client_id in (getattr(settings, name, None) for name in client_id_settings)
                if client_id
            }

            if access_token.application.client_id not in allowed_client_ids:
                raise NotAuthenticated

            return True

    return IsApplication
