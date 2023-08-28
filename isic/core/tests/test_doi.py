import pytest

from isic.core.forms.doi import CreateDoiForm
from isic.core.models.doi import Doi
from isic.core.models.image import Image
from isic.core.services.collection.doi import collection_build_doi, collection_create_doi


@pytest.fixture
def mock_datacite_create_doi(mocker):
    yield mocker.patch("isic.core.services.collection.doi._datacite_create_doi")


@pytest.fixture
def mock_datacite_update_doi(mocker):
    yield mocker.patch("isic.core.services.collection.doi._datacite_update_doi")


@pytest.fixture
def public_collection_with_public_images(image_factory, collection_factory):
    collection = collection_factory(public=True, locked=False)
    collection.images.set([image_factory(public=True) for _ in range(5)])
    return collection


@pytest.fixture
def staff_user_request(staff_user, mocker):
    return mocker.MagicMock(user=staff_user)


@pytest.mark.django_db
def test_collection_create_doi(
    public_collection_with_public_images,
    staff_user,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
):
    collection_create_doi(user=staff_user, collection=public_collection_with_public_images)

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.locked
    assert public_collection_with_public_images.doi
    assert public_collection_with_public_images.doi.creator == staff_user
    mock_datacite_create_doi.assert_called_once()
    mock_datacite_update_doi.assert_called_once()


@pytest.mark.django_db
def test_doi_form_requires_public_collection(private_collection, staff_user_request):
    form = CreateDoiForm(data={}, collection=private_collection, request=staff_user_request)
    assert not form.is_valid()


@pytest.mark.django_db
def test_doi_form_requires_no_existing_doi(public_collection, staff_user_request):
    public_collection.doi = Doi.objects.create(id="foo", creator=staff_user_request.user, url="foo")
    public_collection.save()

    form = CreateDoiForm(
        data={},
        collection=public_collection,
        request=staff_user_request,
    )
    assert not form.is_valid()


@pytest.mark.django_db
def test_doi_form_creation(
    public_collection_with_public_images,
    staff_user_request,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
):
    form = CreateDoiForm(
        data={},
        collection=public_collection_with_public_images,
        request=staff_user_request,
    )
    assert form.is_valid(), form.errors
    form.save()

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.doi is not None
    assert public_collection_with_public_images.locked
    mock_datacite_create_doi.assert_called_once()
    mock_datacite_update_doi.assert_called_once()


@pytest.fixture
def collection_with_several_creators(image_factory, collection_factory, cohort_factory):
    # Cohort A has the most images in collection
    # Cohort B and C have the same number of images in collection
    # Therefore, DOI creation should order A (most), then B and C (alphabetical tie breaker)
    cohort_a, cohort_b, cohort_c = (
        cohort_factory(attribution="Cohort A"),
        cohort_factory(attribution="Cohort B"),
        cohort_factory(attribution="Cohort C"),
    )
    collection = collection_factory(public=True)

    for _ in range(3):
        image_factory(public=True, accession__cohort=cohort_a)

    for _ in range(2):
        image_factory(public=True, accession__cohort=cohort_b)
        image_factory(public=True, accession__cohort=cohort_c)

    collection.images.set(
        Image.objects.filter(accession__cohort__in=[cohort_a, cohort_b, cohort_c])
    )

    return collection, cohort_a, cohort_b, cohort_c


@pytest.mark.django_db
def test_doi_creators_ordered_by_number_images_contributed(collection_with_several_creators, user):
    collection, cohort_a, cohort_b, cohort_c = collection_with_several_creators

    doi = collection_build_doi(collection=collection, doi_id="foo")

    creators = doi["data"]["attributes"]["creators"]

    assert len(creators) == 3
    assert creators[0]["name"] == cohort_a.attribution
    assert creators[1]["name"] == cohort_b.attribution
    assert creators[2]["name"] == cohort_c.attribution


@pytest.mark.django_db
def test_doi_creators_order_anonymous_contributions_last(
    collection_with_several_creators, cohort_factory, image_factory, user
):
    collection, *_ = collection_with_several_creators
    anon_cohort = cohort_factory(attribution="Anonymous")
    # Give anonymous cohort more contributions than others, assert it's still ordered last
    for _ in range(10):
        collection.images.add(image_factory(public=True, accession__cohort=anon_cohort))

    doi = collection_build_doi(collection=collection, doi_id="foo")

    creators = doi["data"]["attributes"]["creators"]

    assert creators[-1]["name"] == "Anonymous"


@pytest.fixture
def collection_with_repeated_creators(image_factory, collection_factory, cohort_factory):
    # Cohort A has the most images in collection
    # Cohort B and C have the same number of images in collection
    # Therefore, DOI creation should order A (most), then B and C (alphabetical tie breaker)
    cohort_a1 = cohort_factory(attribution="Cohort A")
    cohort_a2 = cohort_factory(attribution="Cohort A")
    cohort_b = cohort_factory(attribution="Cohort B")
    collection = collection_factory(public=True)

    for _ in range(3):
        image_factory(public=True, accession__cohort=cohort_a1)
        image_factory(public=True, accession__cohort=cohort_a2)

    for _ in range(2):
        image_factory(public=True, accession__cohort=cohort_b)

    collection.images.set(
        Image.objects.filter(accession__cohort__in=[cohort_a1, cohort_a2, cohort_b])
    )

    return collection, cohort_a1, cohort_a2, cohort_b


@pytest.mark.django_db
def test_doi_creators_collapse_repeated_creators(collection_with_repeated_creators, user):
    collection, cohort_a1, cohort_a2, cohort_b = collection_with_repeated_creators

    doi = collection_build_doi(collection=collection, doi_id="foo")

    creators = doi["data"]["attributes"]["creators"]

    assert creators[0]["name"] == cohort_a1.attribution
    assert creators[1]["name"] == cohort_b.attribution

    assert len(creators) == 2
