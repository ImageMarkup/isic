from django.contrib import admin
import pytest

MODELADMIN_CLASSES = list(admin.site._registry.values())


@pytest.mark.django_db
@pytest.mark.parametrize(
    'modeladmin_class', MODELADMIN_CLASSES, ids=[str(x) for x in MODELADMIN_CLASSES]
)
def test_admin_search_fields(modeladmin_class):
    for field in modeladmin_class.search_fields:
        modeladmin_class.model._default_manager.filter(**{f'{field}__icontains': 'foo'}).count()
