import pytest

from isic.find.find import quickfind_execute


@pytest.mark.django_db
def test_quickfind_hides_certain_groups(user, user_factory):
    user_factory(first_name="foo")
    results = quickfind_execute("foo", user)
    # users aren't in results for non-staff
    assert results == []


@pytest.mark.django_db
def test_quickfind_search_images(user, image):
    results = quickfind_execute(image.isic_id, user)
    assert len(results) == 1
    assert results[0]["title"] == image.isic_id


@pytest.mark.django_db
def test_quickfind_search_private_images(user, image_factory):
    image = image_factory(public=False)
    results = quickfind_execute(image.isic_id, user)
    assert len(results) == 0
