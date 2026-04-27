import pytest

from isic.core.models.image import Image
from isic.core.permissions import get_visible_objects
from isic.core.services.image import share_image


@pytest.fixture
def private_image(image_factory):
    return image_factory(public=False)


@pytest.mark.django_db
def test_image_shares(staff_user, user, private_image):
    assert not user.has_perm("core.view_image", private_image)
    assert get_visible_objects(user, "core.view_image", Image.objects.all()).count() == 0
    share_image(image=private_image, grantor=staff_user, grantee=user)
    assert user.has_perm("core.view_image", private_image)
    assert get_visible_objects(user, "core.view_image", Image.objects.all()).count() == 1


@pytest.mark.django_db
def test_image_shares_idempotent(staff_user, user, private_image):
    assert not user.has_perm("core.view_image", private_image)
    share_image(image=private_image, grantor=staff_user, grantee=user)
    share_image(image=private_image, grantor=staff_user, grantee=user)
    assert user.has_perm("core.view_image", private_image)
