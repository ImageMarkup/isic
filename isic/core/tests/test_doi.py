from pathlib import Path
import tempfile
import zipfile

from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from isic.core.models.doi import Doi
from isic.core.models.image import Image
from isic.core.services.collection.doi import (
    collection_build_doi,
    collection_create_doi,
)
from isic.core.tests.factories import CollectionFactory, DoiFactory


@pytest.fixture
def mock_datacite_citations_fetch(mocker):
    return mocker.patch("isic.core.services.collection.doi.fetch_doi_citations_task")


@pytest.fixture
def mock_datacite_schema_org_dataset_fetch(mocker):
    return mocker.patch("isic.core.services.collection.doi.fetch_doi_schema_org_dataset_task")


@pytest.fixture
def mock_datacite_create_doi(mocker):
    return mocker.patch("isic.core.services.collection.doi._datacite_create_doi")


@pytest.fixture
def mock_datacite_update_doi(mocker):
    return mocker.patch("isic.core.services.collection.doi._datacite_update_doi")


@pytest.fixture
def public_collection_with_public_images(image_factory, collection_factory):
    collection = collection_factory(public=True, locked=False)
    collection.images.set([image_factory(public=True) for _ in range(5)])
    return collection


@pytest.fixture
def staff_user_request(staff_user, mocker):
    return mocker.MagicMock(user=staff_user)


@pytest.mark.django_db(transaction=True)
def test_collection_create_doi(
    public_collection_with_public_images,
    staff_user,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
    mock_datacite_citations_fetch,
    mock_datacite_schema_org_dataset_fetch,
):
    collection_create_doi(user=staff_user, collection=public_collection_with_public_images)

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.locked
    assert public_collection_with_public_images.doi
    assert public_collection_with_public_images.doi.bundle
    assert public_collection_with_public_images.doi.creator == staff_user
    mock_datacite_create_doi.assert_called_once()
    mock_datacite_update_doi.assert_called_once()
    mock_datacite_citations_fetch.delay_on_commit.assert_called_once()
    mock_datacite_schema_org_dataset_fetch.delay_on_commit.assert_called_once()


@pytest.mark.django_db
def test_doi_form_requires_public_collection(staff_user_request):
    collection = CollectionFactory.create(public=False)

    with pytest.raises(ValidationError, match="must be public"):
        collection_create_doi(user=staff_user_request.user, collection=collection)


@pytest.mark.django_db
def test_doi_form_requires_no_existing_doi(staff_user_request):
    collection = CollectionFactory.create(public=True)
    DoiFactory.create(collection=collection, creator=staff_user_request.user)

    with pytest.raises(ValidationError, match="already has a DOI"):
        collection_create_doi(user=staff_user_request.user, collection=collection)


@pytest.mark.django_db(transaction=True)
def test_api_doi_creation(
    public_collection_with_public_images,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
    mock_datacite_citations_fetch,
    mock_datacite_schema_org_dataset_fetch,
    s3ff_random_field_value,
    staff_client,
):
    r = staff_client.post(
        reverse("api:create_doi"),
        {
            "collection_id": public_collection_with_public_images.id,
            "supplemental_files": [
                {
                    "blob": s3ff_random_field_value,
                    "description": "test",
                }
            ],
        },
        content_type="application/json",
    )
    assert r.status_code == 200

    doi = Doi.objects.get(collection=public_collection_with_public_images)
    assert doi.supplemental_files.count() == 1
    assert doi.supplemental_files.first().description == "test"


@pytest.mark.django_db(transaction=True)
def test_doi_creation(
    public_collection_with_public_images,
    staff_user_request,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
    mock_datacite_citations_fetch,
    mock_datacite_schema_org_dataset_fetch,
):
    collection_create_doi(
        user=staff_user_request.user, collection=public_collection_with_public_images
    )

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.doi is not None
    assert public_collection_with_public_images.locked
    mock_datacite_create_doi.assert_called_once()
    mock_datacite_update_doi.assert_called_once()
    mock_datacite_citations_fetch.delay_on_commit.assert_called_once()
    mock_datacite_schema_org_dataset_fetch.delay_on_commit.assert_called_once()


@pytest.fixture
def collection_with_several_creators(image_factory, collection_factory, cohort_factory):
    # Cohort A has the most images in collection
    # Cohort B and C have the same number of images in collection
    # Therefore, DOI creation should order A (most), then B and C (alphabetical tie breaker)
    cohort_a, cohort_b, cohort_c = (
        cohort_factory(),
        cohort_factory(),
        cohort_factory(),
    )
    collection = collection_factory(public=True)

    for _ in range(3):
        image_factory(public=True, accession__cohort=cohort_a, accession__attribution="Cohort A")

    for _ in range(2):
        image_factory(public=True, accession__cohort=cohort_b, accession__attribution="Cohort B")
        image_factory(public=True, accession__cohort=cohort_c, accession__attribution="Cohort C")

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
    assert creators[0]["name"] == "Cohort A"
    assert creators[1]["name"] == "Cohort B"
    assert creators[2]["name"] == "Cohort C"


@pytest.mark.django_db
def test_doi_creators_order_anonymous_contributions_last(
    collection_with_several_creators, cohort_factory, image_factory, user
):
    collection, *_ = collection_with_several_creators
    anon_cohort = cohort_factory()
    # Give anonymous cohort more contributions than others, assert it's still ordered last
    for _ in range(10):
        collection.images.add(
            image_factory(
                public=True, accession__cohort=anon_cohort, accession__attribution="Anonymous"
            )
        )

    doi = collection_build_doi(collection=collection, doi_id="foo")

    creators = doi["data"]["attributes"]["creators"]

    assert creators[-1]["name"] == "Anonymous"


@pytest.fixture
def collection_with_repeated_creators(image_factory, collection_factory, cohort_factory):
    # Cohort A has the most images in collection
    # Cohort B and C have the same number of images in collection
    # Therefore, DOI creation should order A (most), then B and C (alphabetical tie breaker)
    cohort_a1 = cohort_factory()
    cohort_a2 = cohort_factory()
    cohort_b = cohort_factory()
    collection = collection_factory(public=True)

    for _ in range(3):
        image_factory(public=True, accession__cohort=cohort_a1, accession__attribution="Cohort A")
        image_factory(public=True, accession__cohort=cohort_a2, accession__attribution="Cohort A")

    for _ in range(2):
        image_factory(public=True, accession__cohort=cohort_b, accession__attribution="Cohort B")

    collection.images.set(
        Image.objects.filter(accession__cohort__in=[cohort_a1, cohort_a2, cohort_b])
    )

    return collection, cohort_a1, cohort_a2, cohort_b


@pytest.mark.django_db
def test_doi_creators_collapse_repeated_creators(collection_with_repeated_creators, user):
    collection, cohort_a1, cohort_a2, cohort_b = collection_with_repeated_creators

    doi = collection_build_doi(collection=collection, doi_id="foo")

    creators = doi["data"]["attributes"]["creators"]

    assert creators[0]["name"] == "Cohort A"
    assert creators[1]["name"] == "Cohort B"

    assert len(creators) == 2


@pytest.mark.django_db(transaction=True)
def test_doi_files(
    image_factory,
    collection_factory,
    staff_user,
    mock_datacite_create_doi,
    mock_datacite_update_doi,
    mock_datacite_citations_fetch,
    mock_datacite_schema_org_dataset_fetch,
):
    collection = collection_factory(public=True)
    images = [image_factory(public=True) for _ in range(3)]
    collection.images.set(images)

    doi = collection_create_doi(user=staff_user, collection=collection)

    doi.refresh_from_db()

    assert doi.bundle is not None
    assert doi.bundle_size > 0

    assert doi.metadata is not None
    assert doi.metadata_size > 0

    with tempfile.TemporaryDirectory() as temp_dir, zipfile.ZipFile(doi.bundle) as zf:
        zf.extractall(temp_dir)

        for image in images:
            image_path = f"images/{image.isic_id}.jpg"
            assert (Path(temp_dir) / image_path).exists()

        assert (Path(temp_dir) / "metadata.csv").exists()

        licenses = {images[0].accession.copyright_license for image in images}
        for license_ in licenses:
            assert (Path(temp_dir) / f"licenses/{license_}.txt").exists()

        assert (Path(temp_dir) / "attribution.txt").exists()
