import logging

from ninja.operation import PathView
from sentry_sdk import set_tag

logger = logging.getLogger(__name__)


# See https://github.com/vitalik/django-ninja/issues/283.
# This exists to allow the header based authentication to be exempt from CSRF checks,
# while still enforcing CSRF checks on the session based authentication.
class ExemptBearerAuthFromCSRFMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        klass = getattr(view_func, "__self__", None)
        if klass and isinstance(klass, PathView):
            request._dont_enforce_csrf_checks = True  # noqa: SLF001


class LogRequestUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # always run the logger after the view has been called. django-ninja does auth inside of
        # the view and sometimes authentications uses OAuth, so request.user won't be set until the
        # view has been called.

        # certain requests, like static files, don't have a user attribute on the request
        if hasattr(request, "user"):
            logger.info(
                f"{request.method} {request.path} user:{getattr(request.user, "pk", "none")}"  # noqa: G004
            )

            if request.user.is_anonymous:
                set_tag("user_type", "anonymous")
            elif request.user.is_staff:
                set_tag("user_type", "logged-in-staff")
            else:
                set_tag("user_type", "logged-in-user")

        return response
