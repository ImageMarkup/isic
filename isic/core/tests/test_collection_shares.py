import pytest

from isic.core.permissions import get_visible_objects
from isic.core.services.collection import collection_share
from isic.core.services.collection.image import collection_add_images


@pytest.fixture()
def private_collection(image_factory, collection_factory):
    collection = collection_factory(public=False)
    image = image_factory(public=False)
    collection_add_images(collection=collection, image=image)
    return collection


@pytest.mark.django_db()
def test_collection_shares(staff_user, user, private_collection):
    private_image = private_collection.images.first()

    assert not user.has_perm("core.view_image", private_image)
    assert get_visible_objects(user, "core.view_image").count() == 0
    assert not user.has_perm("core.view_collection", private_collection)
    assert get_visible_objects(user, "core.view_collection").count() == 0
    collection_share(collection=private_collection, grantor=staff_user, recipient=user)
    assert user.has_perm("core.view_image", private_image)
    assert get_visible_objects(user, "core.view_image").count() == 1
    assert user.has_perm("core.view_collection", private_collection)
    assert get_visible_objects(user, "core.view_collection").count() == 1


@pytest.mark.django_db()
def test_collection_shares_idempotent(staff_user, user, private_collection):
    private_image = private_collection.images.first()

    assert not user.has_perm("core.view_image", private_image)
    assert not user.has_perm("core.view_collection", private_collection)
    collection_share(collection=private_collection, grantor=staff_user, recipient=user)
    collection_share(collection=private_collection, grantor=staff_user, recipient=user)
    assert user.has_perm("core.view_image", private_image)
    assert user.has_perm("core.view_collection", private_collection)


@pytest.mark.django_db()
def test_collection_shares_beget_image_shares(staff_user, user, private_collection, image_factory):
    private_image = private_collection.images.first()
    collection_share(collection=private_collection, grantor=staff_user, recipient=user)
    assert user.has_perm("core.view_image", private_image)
    assert get_visible_objects(user, "core.view_image").count() == 1

    # adding a new private image to the collection should enable it to be visible to the user
    new_private_image = image_factory(public=False)
    collection_add_images(collection=private_collection, image=new_private_image)

    assert user.has_perm("core.view_image", new_private_image)
    assert get_visible_objects(user, "core.view_image").count() == 2
