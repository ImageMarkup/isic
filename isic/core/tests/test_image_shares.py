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


@pytest.mark.django_db
def test_image_shares_do_not_multiply_images(user, image_factory, image_share_factory):
    private_image = image_factory(public=False)
    public_image = image_factory(public=True)
    # several share rows per image: two grantors for the user, and two other grantees
    image_share_factory(image=private_image, grantee=user)
    image_share_factory(image=private_image, grantee=user)
    image_share_factory(image=public_image)
    image_share_factory(image=public_image)

    # the filter is applied without distinct()
    qs = get_visible_objects(user, "core.view_image", Image.objects.all())
    assert sorted(qs.values_list("pk", flat=True)) == sorted([private_image.pk, public_image.pk])
    assert qs.count() == 2
