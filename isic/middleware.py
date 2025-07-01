import logging

from sentry_sdk import set_tag

logger = logging.getLogger(__name__)


class UserTypeTagMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # always run the logger after the view has been called. django-ninja does auth inside of
        # the view and sometimes authentications uses OAuth, so request.user won't be set until the
        # view has been called.

        # certain requests, like static files, don't have a user attribute on the request
        if hasattr(request, "user"):
            if request.user.is_anonymous:
                set_tag("user_type", "anonymous")
            elif request.user.is_staff:
                set_tag("user_type", "logged-in-staff")
            else:
                set_tag("user_type", "logged-in-user")

        return response
