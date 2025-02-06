from functools import wraps
from urllib.parse import urlparse

import django.apps
from django.apps import apps
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db.models import Model
from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404, resolve_url
from ninja.security.session import SessionAuth


class SessionAuthStaffUser(SessionAuth):
    def authenticate(self, request: HttpRequest, key: str | None) -> User | None:
        if request.user.is_staff:
            return request.user

        return None


class UserPermissions:
    model = User
    perms = ["view_staff"]
    filters = {}

    @staticmethod
    def view_staff(user_obj, _=None):
        return user_obj.is_staff


User.perms_class = UserPermissions  # type: ignore[attr-defined]


ISIC_PERMS_MAP = {}
ISIC_FILTERS_MAP = {}
for model in django.apps.apps.get_models():
    name = model.__name__
    if hasattr(model, "perms_class"):
        for perm in model.perms_class.perms:
            ISIC_PERMS_MAP[f"{model._meta.app_label}.{perm}"] = getattr(model.perms_class, perm)

        for perm, filter_name in model.perms_class.filters.items():
            ISIC_FILTERS_MAP[f"{model._meta.app_label}.{perm}"] = getattr(
                model.perms_class, filter_name
            )


class IsicObjectPermissionsBackend(BaseBackend):
    def has_perm(self, user_obj, perm, obj=None):
        if ISIC_PERMS_MAP.get(perm):
            return ISIC_PERMS_MAP[perm](user_obj, obj)


def get_visible_objects(user, perm, qs=None):
    filter_func = ISIC_FILTERS_MAP.get(perm)

    if filter_func:
        return filter_func(user, qs)

    raise Exception(f"No permission registered: {perm}")


# this code is adapted from the login_required decorator, it's
# useful for building the redirect url with a ?next= component.
def _redirect_to_login(request):
    path = request.build_absolute_uri()
    resolved_login_url = resolve_url(settings.LOGIN_URL)
    # If the login url is the same scheme and net location then just
    # use the path as the "next" url.
    login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
    current_scheme, current_netloc = urlparse(path)[:2]
    if (not login_scheme or login_scheme == current_scheme) and (
        not login_netloc or login_netloc == current_netloc
    ):
        path = request.get_full_path()
    return redirect_to_login(path, resolved_login_url)


# This is a decorator adapted from django-guardian
def needs_object_permission(perm: str, lookup_variables=None):  # noqa: C901
    def decorator(view_func):  # noqa: C901
        def _wrapped_view(request, *args, **kwargs):
            # if more than one parameter is passed to the decorator we try to
            # fetch object for which check would be made
            obj = None
            if lookup_variables:
                model, lookups = lookup_variables[0], lookup_variables[1:]
                # Parse model
                if isinstance(model, str):
                    splitted = model.split(".")
                    if len(splitted) != 2:
                        raise Exception(
                            "If model should be looked up from "
                            "string it needs format: 'app_label.ModelClass'"
                        )
                    model = apps.get_model(*splitted)  # type: ignore[arg-type]
                elif issubclass(model.__class__, Model | ModelBase | QuerySet):
                    pass
                else:
                    msg = (
                        "First lookup argument must always be "
                        "a model, string pointing at app/model or queryset. "
                        f"Given: {model} (type: {type(model)})"
                    )
                    raise Exception(msg)
                # Parse lookups
                if len(lookups) % 2 != 0:
                    raise Exception(
                        "Lookup variables must be provided as pairs of lookup_string and view_arg"
                    )
                lookup_dict = {}
                for lookup, view_arg in zip(lookups[::2], lookups[1::2], strict=False):
                    if view_arg not in kwargs:
                        msg = f"Argument {view_arg} was not passed into view function"
                        raise Exception(msg)
                    lookup_dict[lookup] = kwargs[view_arg]
                obj = get_object_or_404(model, **lookup_dict)

            if not request.user.has_perm(perm, obj):
                if not request.user.is_authenticated:
                    return _redirect_to_login(request)

                raise PermissionDenied

            return view_func(request, *args, **kwargs)

        return wraps(view_func)(_wrapped_view)

    return decorator
