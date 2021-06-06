import django.apps
from django.apps import apps
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.db.models import Model
from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils.functional import wraps


class UserPermissions:
    model = User
    perms = ['view_staff']
    filters = {}

    @staticmethod
    def view_staff(user_obj, obj=None):
        return user_obj.is_active and user_obj.is_staff


User.perms_class = UserPermissions


ISIC_PERMS_MAP = {}
ISIC_FILTERS_MAP = {}
for model in django.apps.apps.get_models():
    name = model.__name__
    if hasattr(model, 'perms_class'):
        for perm in model.perms_class.perms:
            ISIC_PERMS_MAP[f'{model._meta.app_label}.{perm}'] = getattr(model.perms_class, perm)

        for perm, filter_name in model.perms_class.filters.items():
            ISIC_FILTERS_MAP[f'{model._meta.app_label}.{perm}'] = getattr(
                model.perms_class, filter_name
            )


class IsicObjectPermissionsBackend(BaseBackend):
    def has_perm(self, user_obj, perm, obj=None):
        if ISIC_PERMS_MAP.get(perm):
            return ISIC_PERMS_MAP[perm](user_obj, obj)


def get_visible_objects(user, perm, qs=None):
    filter = ISIC_FILTERS_MAP.get(perm)

    if filter:
        return filter(user, qs)
    else:
        raise Exception(f'No permission registered: {perm}')


# This is a decorator adapted from django-guardian
def permission_or_404(perm, lookup_variables=None, **kwargs):
    # Check if perm is given as string in order not to decorate
    # view function itself which makes debugging harder
    if not isinstance(perm, str):
        raise Exception(
            'First argument must be in format: '
            "'app_label.codename or a callable which return similar string'"
        )

    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            # if more than one parameter is passed to the decorator we try to
            # fetch object for which check would be made
            obj = None
            if lookup_variables:
                model, lookups = lookup_variables[0], lookup_variables[1:]
                # Parse model
                if isinstance(model, str):
                    splitted = model.split('.')
                    if len(splitted) != 2:
                        raise Exception(
                            'If model should be looked up from '
                            "string it needs format: 'app_label.ModelClass'"
                        )
                    model = apps.get_model(*splitted)
                elif issubclass(model.__class__, (Model, ModelBase, QuerySet)):
                    pass
                else:
                    raise Exception(
                        'First lookup argument must always be '
                        'a model, string pointing at app/model or queryset. '
                        'Given: %s (type: %s)' % (model, type(model))
                    )
                # Parse lookups
                if len(lookups) % 2 != 0:
                    raise Exception(
                        'Lookup variables must be provided '
                        'as pairs of lookup_string and view_arg'
                    )
                lookup_dict = {}
                for lookup, view_arg in zip(lookups[::2], lookups[1::2]):
                    if view_arg not in kwargs:
                        raise Exception('Argument %s was not passed into view function' % view_arg)
                    lookup_dict[lookup] = kwargs[view_arg]
                obj = get_object_or_404(model, **lookup_dict)

            if not request.user.has_perm(perm, obj):
                raise Http404

            return view_func(request, *args, **kwargs)

        return wraps(view_func)(_wrapped_view)

    return decorator
