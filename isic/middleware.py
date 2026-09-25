from collections.abc import Callable
import logging
from typing import Any

from allauth.account.views import logout
from django.http import HttpRequest, HttpResponseBase, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import urlencode
from sentry_sdk import set_tag

from isic.core.views.terms_of_use import terms_of_use
from isic.login.views import accept_terms_of_use

logger = logging.getLogger(__name__)


class SentryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # always run the logger after the view has been called. DRF does auth inside of the view
        # and sometimes authentication uses OAuth, so request.user won't be set until the view has
        # been called.

        # certain requests, like static files, don't have a user attribute on the request
        if hasattr(request, "user"):
            if request.user.is_anonymous:
                set_tag("user_type", "anonymous")
            elif request.user.is_staff:
                set_tag("user_type", "logged-in-staff")
            else:
                set_tag("user_type", "logged-in-user")

        return response


TERMS_EXEMPT_VIEWS = {logout, terms_of_use, accept_terms_of_use}


class TermsOfUseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponseBase],
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> HttpResponseBase | None:
        if (
            not request.user.is_authenticated
            or request.path_info.startswith("/api/")
            or view_func in TERMS_EXEMPT_VIEWS
            or request.user.profile.accepted_terms is not None
        ):
            return None

        return HttpResponseRedirect(
            f"{reverse('login/accept-terms')}?{urlencode({'next': request.get_full_path()})}"
        )
