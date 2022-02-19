from django.core.exceptions import ValidationError
from django.urls.base import reverse
import pytest

from isic.core.models.collection import Collection


@pytest.fixture
def locked_collection(collection_factory, user):
    return collection_factory(locked=True, creator=user)


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


@pytest.mark.django_db
def test_collection_locked_modifications(locked_collection):
    with pytest.raises(ValidationError):
        locked_collection.name = 'foo'
        locked_collection.save()


@pytest.mark.django_db(transaction=True)
def test_collection_locked_add_images(locked_collection, image):
    # test both sides
    with pytest.raises(ValidationError):
        locked_collection.images.add(image)

    with pytest.raises(ValidationError):
        image.collections.add(locked_collection)


@pytest.mark.skip('Unimplemented')
def test_collection_locked_add_doi():
    # TODO: should be able to register a DOI on a locked collection
    pass


@pytest.mark.django_db(transaction=True)
def test_public_collection_add_private_images(public_collection, image_factory):
    image = image_factory(public=False)

    with pytest.raises(ValidationError):
        public_collection.images.add(image)

    with pytest.raises(ValidationError):
        image.collections.add(public_collection)


@pytest.mark.django_db
def test_make_private_collection_public(private_collection, image_factory):
    image = image_factory(public=False)
    private_collection.images.add(image)

    with pytest.raises(ValidationError):
        private_collection.public = True
        private_collection.save(update_fields=['public'])
