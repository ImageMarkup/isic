from django.urls.base import reverse
import pytest

from isic.core.models.collection import Collection


@pytest.mark.django_db
def test_collection_form(authenticated_client, user):
    r = authenticated_client.post(
        reverse('core/collection-create'), {'name': 'foo', 'description': 'bar', 'public': False}
    )
    assert r.status_code == 302
    collection = Collection.objects.first()
    assert collection.creator == user
    assert collection.name == 'foo'
    assert collection.description == 'bar'
    assert collection.public is False
