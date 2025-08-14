import pytest
from pytest_lazy_fixtures import lf

from isic.core.tests.factories import CollectionFactory, DoiFactory
from isic.find.find import quickfind_execute


@pytest.mark.django_db
def test_quickfind_hides_certain_groups(user, user_factory):
    user_factory(first_name="foo")
    results = quickfind_execute("foo", user)
    # users aren't in results for non-staff
    assert results == []


@pytest.mark.django_db
def test_quickfind_search_images(user, image_factory):
    image = image_factory(public=True)
    results = quickfind_execute(image.isic_id, user)
    assert len(results) == 1
    assert results[0]["title"] == image.isic_id


@pytest.mark.django_db
def test_quickfind_search_private_images(user, image_factory):
    image = image_factory(public=False)
    results = quickfind_execute(image.isic_id, user)
    assert len(results) == 0


@pytest.mark.django_db
def test_quickfind_search_dois(user):
    doi = DoiFactory.create(
        collection=CollectionFactory.create(name="foo"),
        is_draft=False,
    )
    results = quickfind_execute(doi.collection.name, user)
    doi_results = [r for r in results if r["result_type"] == "DOI"]
    assert len(doi_results) == 1
    assert doi_results[0]["title"] == doi.collection.name


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("user_", "expected_count"),
    [
        (lf("user"), 0),
        (lf("staff_user"), 1),
    ],
)
def test_quickfind_search_draft_dois_visibility(user_, expected_count):
    doi = DoiFactory.create(
        collection=CollectionFactory.create(name="foo"),
        is_draft=True,
    )
    results = quickfind_execute(doi.collection.name, user_)
    doi_results = [r for r in results if r["result_type"] == "DOI"]
    assert len(doi_results) == expected_count
    if expected_count:
        assert doi_results[0]["title"] == doi.collection.name
