from ninja.operation import PathView


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
            request._dont_enforce_csrf_checks = True
