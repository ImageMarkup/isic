from pathlib import Path
import tempfile
import zipfile

from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.api.doi import RelatedIdentifierIn
from isic.core.models.doi import Doi, DraftDoi
from isic.core.models.image import Image
from isic.core.services.collection.doi import (
    collection_build_doi,
    collection_create_draft_doi,
    draft_doi_publish,
)
from isic.core.tests.factories import CollectionFactory, DoiFactory


@pytest.fixture
def mock_datacite_create_draft_doi(mocker):
    return mocker.patch("isic.core.services.collection.doi._datacite_create_draft_doi")


@pytest.fixture
def mock_datacite_promote_draft_doi_to_findable(mocker):
    return mocker.patch("isic.core.services.collection.doi._datacite_promote_draft_doi_to_findable")


@pytest.fixture
def public_collection_with_public_images(image_factory, collection_factory):
    collection = collection_factory(public=True, locked=False)
    collection.images.set([image_factory(public=True) for _ in range(5)])
    return collection


@pytest.mark.django_db(transaction=True)
def test_create_draft_doi(
    public_collection_with_public_images,
    staff_user,
    mock_datacite_create_draft_doi,
    mock_datacite_promote_draft_doi_to_findable,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
):
    draft_doi = collection_create_draft_doi(
        user=staff_user, collection=public_collection_with_public_images
    )
    draft_doi.refresh_from_db()

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.draftdoi is not None
    assert public_collection_with_public_images.locked
    assert mock_datacite_create_draft_doi.call_count == 1
    assert mock_datacite_promote_draft_doi_to_findable.call_count == 0
    assert mock_fetch_doi_citations.call_count == 1
    assert mock_fetch_doi_schema_org_dataset.call_count == 1
    assert draft_doi.citations == {
        "apa": "fake citation",
        "chicago": "fake citation",
    }
    assert draft_doi.schema_org_dataset == {
        "@type": "Dataset",
        "name": "fake dataset",
        "isAccessibleForFree": True,
    }


@pytest.mark.django_db(transaction=True)
def test_collection_create_draft_and_publish_doi(
    public_collection_with_public_images,
    staff_user,
    mock_datacite_create_draft_doi,
    mock_datacite_promote_draft_doi_to_findable,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
):
    draft_doi = collection_create_draft_doi(
        user=staff_user, collection=public_collection_with_public_images
    )
    draft_doi.refresh_from_db()

    public_collection_with_public_images.refresh_from_db()
    assert public_collection_with_public_images.locked
    assert public_collection_with_public_images.draftdoi
    assert public_collection_with_public_images.draftdoi.bundle
    assert public_collection_with_public_images.draftdoi.creator == staff_user
    assert mock_datacite_create_draft_doi.call_count == 1
    assert mock_datacite_promote_draft_doi_to_findable.call_count == 0
    assert draft_doi.citations == {"apa": "fake citation", "chicago": "fake citation"}
    assert draft_doi.schema_org_dataset == {
        "@type": "Dataset",
        "name": "fake dataset",
        "isAccessibleForFree": True,
    }

    doi = draft_doi_publish(user=staff_user, draft_doi=draft_doi)
    doi.refresh_from_db()
    public_collection_with_public_images.refresh_from_db()

    assert public_collection_with_public_images.doi
    assert (
        not hasattr(public_collection_with_public_images, "draftdoi")
        or public_collection_with_public_images.draftdoi is None
    )
    assert mock_datacite_promote_draft_doi_to_findable.call_count == 1


@pytest.mark.django_db
def test_draft_doi_allows_private_collection(
    staff_user,
    image_factory,
    mock_datacite_create_draft_doi,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
):
    collection = CollectionFactory.create(public=False)
    collection.images.set([image_factory(public=False)])
    collection_create_draft_doi(user=staff_user, collection=collection)


@pytest.mark.django_db
def test_draft_doi_form_requires_no_existing_doi(staff_user, image_factory):
    collection = CollectionFactory.create(public=True)
    collection.images.set([image_factory(public=True)])
    DoiFactory.create(collection=collection, creator=staff_user)

    with pytest.raises(ValidationError, match="already has a DOI"):
        collection_create_draft_doi(user=staff_user, collection=collection)


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

    doi = collection_build_doi(collection=collection, doi_id="foo", is_draft=False)

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

    doi = collection_build_doi(collection=collection, doi_id="foo", is_draft=False)

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

    doi = collection_build_doi(collection=collection, doi_id="foo", is_draft=False)

    creators = doi["data"]["attributes"]["creators"]

    assert creators[0]["name"] == "Cohort A"
    assert creators[1]["name"] == "Cohort B"

    assert len(creators) == 2


@pytest.mark.django_db(transaction=True)
def test_doi_files(
    image_factory,
    collection_factory,
    staff_user,
    mock_datacite_create_draft_doi,
    mock_datacite_promote_draft_doi_to_findable,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
):
    collection = collection_factory(public=True)
    images = [image_factory(public=True) for _ in range(3)]
    collection.images.set(images)

    draft_doi = collection_create_draft_doi(user=staff_user, collection=collection)
    doi = draft_doi_publish(user=staff_user, draft_doi=draft_doi)

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


@pytest.mark.django_db(transaction=True)
def test_api_doi_creation(
    public_collection_with_public_images,
    mock_datacite_create_draft_doi,
    mock_datacite_promote_draft_doi_to_findable,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
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
                    "description": "test supplemental file",
                }
            ],
            "related_identifiers": [
                {
                    "relation_type": "IsReferencedBy",
                    "related_identifier_type": "DOI",
                    "related_identifier": "10.1000/182",
                },
                {
                    "relation_type": "IsSupplementedBy",
                    "related_identifier_type": "URL",
                    "related_identifier": "https://example.com/supplemental-data",
                },
            ],
        },
        content_type="application/json",
    )
    assert r.status_code == 201

    draft_doi = DraftDoi.objects.get(collection=public_collection_with_public_images)
    assert draft_doi.supplemental_files.count() == 1
    assert draft_doi.supplemental_files.first().description == "test supplemental file"

    assert draft_doi.related_identifiers.count() == 2

    doi_related = draft_doi.related_identifiers.get(related_identifier_type="DOI")
    assert doi_related.relation_type == "IsReferencedBy"
    assert doi_related.related_identifier == "10.1000/182"

    url_related = draft_doi.related_identifiers.get(related_identifier_type="URL")
    assert url_related.relation_type == "IsSupplementedBy"
    assert url_related.related_identifier == "https://example.com/supplemental-data"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("related_identifier_type", "related_identifier"),
    [
        ("DOI", "invalid-doi-format"),
        ("URL", "not-a-valid-url"),
    ],
)
def test_api_doi_creation_invalid_related_identifiers(
    public_collection_with_public_images,
    staff_client,
    related_identifier_type,
    related_identifier,
):
    r = staff_client.post(
        reverse("api:create_doi"),
        {
            "collection_id": public_collection_with_public_images.id,
            "supplemental_files": [],
            "related_identifiers": [
                {
                    "relation_type": "IsReferencedBy",
                    "related_identifier_type": related_identifier_type,
                    "related_identifier": related_identifier,
                }
            ],
        },
        content_type="application/json",
    )
    assert r.status_code == 422


@pytest.mark.django_db
def test_api_doi_creation_invalid_related_identifier_relation_type(
    public_collection_with_public_images,
    staff_client,
):
    r = staff_client.post(
        reverse("api:create_doi"),
        {
            "collection_id": public_collection_with_public_images.id,
            "supplemental_files": [],
            "related_identifiers": [
                {
                    "relation_type": "InvalidRelationType",
                    "related_identifier_type": "DOI",
                    "related_identifier": "10.1000/182",
                }
            ],
        },
        content_type="application/json",
    )
    # TODO: 422 vs 400
    assert r.status_code == 422


@pytest.mark.django_db
def test_api_doi_creation_invalid_related_identifier_relation_identifier_type(
    public_collection_with_public_images,
    staff_client,
):
    r = staff_client.post(
        reverse("api:create_doi"),
        {
            "collection_id": public_collection_with_public_images.id,
            "supplemental_files": [],
            "related_identifiers": [
                {
                    "relation_type": "IsReferencedBy",
                    "related_identifier_type": "InvalidType",
                    "related_identifier": "10.1000/182",
                }
            ],
        },
        content_type="application/json",
    )
    # TODO: should we be returning 422 or 400
    assert r.status_code == 422


@pytest.mark.django_db
def test_collection_create_doi_view_with_existing_doi(
    public_collection_with_public_images, staff_client, staff_user
):
    # Create a DOI for the collection
    doi = DoiFactory.create(collection=public_collection_with_public_images, creator=staff_user)

    # Try to access the create DOI view
    r = staff_client.get(
        reverse("core/collection-create-doi", args=[public_collection_with_public_images.pk])
    )

    # Should redirect to the DOI detail page
    assert r.status_code == 302
    assert r.url == reverse("core/doi-detail", args=[doi.slug])


@pytest.mark.django_db(transaction=True)
def test_draft_doi_complete_lifecycle(  # noqa: PLR0915
    image_factory,
    collection_factory,
    staff_user,
    staff_client,
    mock_datacite_create_draft_doi,
    mock_datacite_promote_draft_doi_to_findable,
    mock_fetch_doi_citations,
    mock_fetch_doi_schema_org_dataset,
    s3ff_random_field_value,
):
    from isic.core.models.doi import DraftDoi

    # create private collection with private images
    collection = collection_factory(public=False, locked=False)
    private_images = []
    for i in range(3):
        image = image_factory(public=False)
        image.accession.attribution = f"Test Institution {i + 1}"
        image.accession.copyright_license = "CC-BY"
        image.accession.save()
        private_images.append(image)

    collection.images.set(private_images)
    collection.save()

    assert not collection.public
    assert not collection.locked
    assert collection.images.count() == 3
    assert all(not img.public for img in collection.images.all())
    assert not hasattr(collection, "doi")
    assert not hasattr(collection, "draftdoi")

    supplemental_files = [
        {
            "blob": S3PlaceholderFile.from_field(s3ff_random_field_value),
            "description": "Test supplemental file",
        }
    ]

    related_identifiers = [
        RelatedIdentifierIn(
            relation_type="IsReferencedBy",
            related_identifier_type="DOI",
            related_identifier="10.1000/182",
        ),
        RelatedIdentifierIn(
            relation_type="IsSupplementedBy",
            related_identifier_type="URL",
            related_identifier="https://example.com/supplement",
        ),
    ]

    draft_doi = collection_create_draft_doi(
        user=staff_user,
        collection=collection,
        supplemental_files=supplemental_files,
        related_identifiers=related_identifiers,
    )

    draft_doi.refresh_from_db()
    collection.refresh_from_db()

    assert isinstance(draft_doi, DraftDoi)
    assert collection.locked
    assert hasattr(collection, "draftdoi")
    assert collection.draftdoi == draft_doi
    assert draft_doi.creator == staff_user
    assert draft_doi.collection == collection

    assert draft_doi.supplemental_files.count() == 1
    supplemental_file = draft_doi.supplemental_files.first()
    assert supplemental_file.description == "Test supplemental file"

    assert draft_doi.related_identifiers.count() == 2
    related_ids = list(draft_doi.related_identifiers.all())
    assert any(r.relation_type == "IsReferencedBy" for r in related_ids)
    assert any(r.relation_type == "IsSupplementedBy" for r in related_ids)

    assert not collection.public
    assert all(not img.public for img in collection.images.all())

    assert mock_datacite_create_draft_doi.call_count == 1
    assert mock_datacite_promote_draft_doi_to_findable.call_count == 0

    assert draft_doi.bundle is not None
    assert draft_doi.citations == {"apa": "fake citation", "chicago": "fake citation"}
    assert draft_doi.schema_org_dataset == {
        "@type": "Dataset",
        "name": "fake dataset",
        "isAccessibleForFree": True,
    }

    draft_doi_id = draft_doi.id
    final_doi = draft_doi_publish(user=staff_user, draft_doi=draft_doi)

    final_doi.refresh_from_db()
    collection.refresh_from_db()

    assert isinstance(final_doi, Doi)
    assert final_doi.id == draft_doi_id
    with pytest.raises(DraftDoi.DoesNotExist):
        DraftDoi.objects.get(id=draft_doi_id)

    assert hasattr(collection, "doi")
    assert collection.doi == final_doi
    assert not hasattr(collection, "draftdoi")
    assert collection.locked

    assert collection.public

    for image in collection.images.all():
        image.refresh_from_db()
        image.accession.refresh_from_db()
        assert image.public
        assert image.accession.sponsored_blob

    assert final_doi.creator == staff_user
    assert final_doi.collection == collection
    assert final_doi.bundle is not None
    assert final_doi.citations == {"apa": "fake citation", "chicago": "fake citation"}
    assert final_doi.schema_org_dataset == {
        "@type": "Dataset",
        "name": "fake dataset",
        "isAccessibleForFree": True,
    }

    assert final_doi.supplemental_files.count() == 1
    final_supplemental_file = final_doi.supplemental_files.first()
    assert final_supplemental_file.description == "Test supplemental file"

    assert final_doi.related_identifiers.count() == 2
    final_related_ids = list(final_doi.related_identifiers.all())
    assert any(r.relation_type == "IsReferencedBy" for r in final_related_ids)
    assert any(r.relation_type == "IsSupplementedBy" for r in final_related_ids)

    assert mock_datacite_promote_draft_doi_to_findable.call_count == 1

    assert final_doi.bundle is not None
    assert final_doi.bundle_size > 0
    assert final_doi.metadata is not None
    assert final_doi.metadata_size > 0
