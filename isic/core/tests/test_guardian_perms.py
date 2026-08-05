from django.core.cache import cache
from django.db import transaction
from guardian.shortcuts import get_objects_for_user
from guardian.utils import get_anonymous_user
import pytest

from isic.core.guardian_permissions import initialize_guardian_permissions
from isic.core.models.image import ImageShare


@pytest.mark.django_db
def test_initialize_guardian_permissions(suppress_post_save_signals, image_factory, user_factory):
    # To test that permissions are applied correctly to existing objects,
    # disable post_save signals for this test, then create objects
    public_image = image_factory(public=True)
    private_image = image_factory(public=False)
    contributor_image = image_factory(public=False)
    contributor_owner = user_factory(is_staff=False)
    contributor = contributor_image.accession.cohort.contributor
    contrib_group = f"contributor_{contributor.id}"
    contributor.owners.add(contributor_owner)
    nonstaff_user = user_factory(is_staff=False)
    staff_user = user_factory(is_staff=True)
    ImageShare.objects.create(grantor=staff_user, grantee=nonstaff_user, image=private_image)

    # Check that no permissions are applied prior to initialization
    for user in [contributor_owner, nonstaff_user, staff_user]:
        assert user.groups.count() == 0
        qs = get_objects_for_user(user, "core.view_image")
        assert qs.count() == 0

    initialize_guardian_permissions()

    assert {group.name for group in contributor_owner.groups.all()} == {"Public", contrib_group}
    contrib_qs = get_objects_for_user(contributor_owner, "core.view_image")
    assert set(contrib_qs) == {public_image, contributor_image}

    assert {group.name for group in nonstaff_user.groups.all()} == {"Public"}
    nonstaff_qs = get_objects_for_user(nonstaff_user, "core.view_image")
    assert set(nonstaff_qs) == {public_image, private_image}

    assert {group.name for group in staff_user.groups.all()} == {"Public", "ISIC Staff"}
    staff_qs = get_objects_for_user(staff_user, "core.view_image")
    assert set(staff_qs) == {public_image, private_image, contributor_image}


@pytest.mark.django_db
def test_view_image_permission_assignment(
    nonstaff_user, staff_user, public_image, private_image, image_factory
):
    private_contrib_image = image_factory(public=False)
    contributor = private_contrib_image.accession.cohort.contributor
    contributor.owners.add(nonstaff_user)
    contributor.save()

    # Anon user has access to only public images, no metadata access
    anon = get_anonymous_user()
    anon_qs = get_objects_for_user(anon, "core.view_image")
    assert set(anon_qs) == {public_image}
    anon_qs = get_objects_for_user(anon, "core.view_image_metadata")
    assert not set(anon_qs)

    # Nonstaff user has access to public image and private image where they are a contributor owner
    user_qs = get_objects_for_user(nonstaff_user, "core.view_image")
    assert set(user_qs) == {public_image, private_contrib_image}
    # Create an ImageShare so they can see the other private image
    ImageShare.objects.create(image=private_image, grantor=staff_user, grantee=nonstaff_user)
    user_qs = get_objects_for_user(nonstaff_user, "core.view_image")
    assert set(user_qs) == {public_image, private_image, private_contrib_image}
    # Metadata access only on image where they are a contributor owner
    user_qs = get_objects_for_user(nonstaff_user, "core.view_image_metadata")
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
    qs = get_objects_for_user(staff_user, "core.view_image")
    assert qs.count() == 10
    # Cache hit means no queries required
    with django_assert_num_queries(0):
        get_objects_for_user(staff_user, "core.view_image")
