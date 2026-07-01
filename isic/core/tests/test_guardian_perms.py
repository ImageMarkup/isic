from django.core.cache import cache
from django.db import transaction
from guardian.shortcuts import get_objects_for_user
from guardian.utils import get_anonymous_user
import pytest

from isic.core.models.image import ImageShare


@pytest.mark.django_db
def test_view_image_permission_assignment(
    user, staff_user, public_image, private_image, image_factory
):
    private_contrib_image = image_factory(public=False)
    contributor = private_contrib_image.accession.cohort.contributor
    contributor.owners.add(user)
    contributor.save()

    # Anon user has access to only public images, no metadata access
    anon = get_anonymous_user()
    anon_qs = get_objects_for_user(anon, "core.view_image")
    assert set(anon_qs) == {public_image}
    anon_qs = get_objects_for_user(anon, "core.view_image_metadata")
    assert not set(anon_qs)

    # Nonstaff user has access to public image and private image where they are a contributor owner
    user_qs = get_objects_for_user(user, "core.view_image")
    assert set(user_qs) == {public_image, private_contrib_image}
    # Create an ImageShare so they can see the other private image
    ImageShare.objects.create(image=private_image, grantor=staff_user, grantee=user)
    user_qs = get_objects_for_user(user, "core.view_image")
    assert set(user_qs) == {public_image, private_image, private_contrib_image}
    # Metadata access only on image where they are a contributor owner
    user_qs = get_objects_for_user(user, "core.view_image_metadata")
    assert set(user_qs) == {private_contrib_image}

    # Staff user has access to all images, all metadata
    staff_qs = get_objects_for_user(staff_user, "core.view_image")
    assert set(staff_qs) == {public_image, private_contrib_image, private_image}
    staff_qs = get_objects_for_user(staff_user, "core.view_image_metadata")
    assert set(staff_qs) == {public_image, private_contrib_image, private_image}


@pytest.mark.django_db
def test_list_images_cache_hit(staff_user, image_factory, django_assert_num_queries):
    with transaction.atomic():
        image_factory.create_batch(10)

    cache.clear()
    get_objects_for_user(staff_user, "core.view_image")
    # Cache hit means no queries required
    with django_assert_num_queries(0):
        get_objects_for_user(staff_user, "core.view_image")
