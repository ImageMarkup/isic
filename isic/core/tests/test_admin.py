from django.contrib import admin
import pytest

from isic.core.admin import StaffReadonlyAdmin

ISIC_MODELADMIN_OBJECTS = [
    o for o in admin.site._registry.values() if o.__module__.startswith("isic")
]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "modeladmin_object", ISIC_MODELADMIN_OBJECTS, ids=[str(x) for x in ISIC_MODELADMIN_OBJECTS]
)
def test_admin_search_fields(modeladmin_object):
    for field in modeladmin_object.search_fields:
        modeladmin_object.model._default_manager.filter(**{f"{field}__icontains": "foo"}).count()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "modeladmin_object", ISIC_MODELADMIN_OBJECTS, ids=[str(x) for x in ISIC_MODELADMIN_OBJECTS]
)
def test_admin_is_readonly_for_staff(modeladmin_object):
    assert isinstance(modeladmin_object, StaffReadonlyAdmin)
