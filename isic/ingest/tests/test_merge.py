from django.core.exceptions import ValidationError
import pytest
from pytest_lazyfixture import lazy_fixture

from isic.core.models.base import CopyrightLicense
from isic.core.models.collection import Collection
from isic.core.models.doi import Doi
from isic.core.services.collection import collection_merge_magic_collections
from isic.core.services.collection.image import collection_add_images
from isic.ingest.models.cohort import Cohort
from isic.ingest.services.cohort import cohort_merge


@pytest.fixture
def full_cohort(cohort_factory, accession_factory, image_factory, collection_factory):
    def _full_cohort():
        collection = collection_factory()
        cohort = cohort_factory(collection=collection)
        accession = accession_factory(cohort=cohort)
        image = image_factory(accession=accession, public=True)
        collection_add_images(collection=collection, image=image)
        return cohort

    return _full_cohort


@pytest.mark.django_db
def test_merge_cohorts(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    # coerce the copyright license to test the happy path
    cohort_a.copyright_license = cohort_b.copyright_license
    cohort_a.save()

    # make sure that the zip_uploads, metadata_files, and accessions from cohort_b are
    # transferred to cohort_a.
    cohort_b_pk = cohort_b.pk
    cohort_b_zip_uploads = cohort_b.zip_uploads.values_list("pk", flat=True)
    cohort_b_metadata_files = cohort_b.metadata_files.values_list("pk", flat=True)
    cohort_b_accessions = cohort_b.accessions.values_list("pk", flat=True)
    cohort_b_magic_coll_images = cohort_b.collection.images.values_list("pk", flat=True)

    cohort_merge(dest_cohort=cohort_a, src_cohort=cohort_b)

    cohort_a.refresh_from_db()
    assert not Cohort.objects.filter(pk=cohort_b_pk).exists()
    assert set(cohort_b_zip_uploads) <= set(cohort_a.zip_uploads.values_list("pk", flat=True))
    assert set(cohort_b_metadata_files) <= set(cohort_a.metadata_files.values_list("pk", flat=True))
    assert set(cohort_b_accessions) <= set(cohort_a.accessions.values_list("pk", flat=True))
    assert set(cohort_b_magic_coll_images) <= set(
        cohort_a.collection.images.values_list("pk", flat=True)
    )


@pytest.mark.django_db
def test_merge_cohorts_missing_magic_collections(full_cohort):
    """Test that merging a cohort into a cohort with no magic collections works."""
    dest_cohort, src_cohort = full_cohort(), full_cohort()
    # coerce the copyright license to test the happy path
    dest_cohort.copyright_license = src_cohort.copyright_license
    dest_cohort.save()
    dest_cohort.collection.delete()
    dest_cohort.refresh_from_db()

    total_cohort_images = set(src_cohort.collection.images.values_list("pk", flat=True))

    cohort_merge(dest_cohort=dest_cohort, src_cohort=src_cohort)
    dest_cohort.refresh_from_db()
    assert set(dest_cohort.collection.images.values_list("pk", flat=True)) == total_cohort_images


@pytest.mark.django_db
def test_merge_cohorts_conflicting_fields(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    # set up mismatching copyright license fields
    cohort_a.copyright_license = CopyrightLicense.CC_0
    cohort_a.save()
    cohort_b.copyright_license = CopyrightLicense.CC_BY
    cohort_b.save()

    with pytest.raises(ValidationError, match="license"):
        cohort_merge(dest_cohort=cohort_a, src_cohort=cohort_b)


@pytest.mark.django_db
def test_merge_cohorts_conflicting_original_blob_names(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    # set up conflicting original blob names
    accession_a, accession_b = cohort_a.accessions.first(), cohort_b.accessions.first()
    accession_a.original_blob_name = "foo"
    accession_a.save()
    accession_b.original_blob_name = "foo"
    accession_b.save()

    with pytest.raises(ValidationError, match="blob names"):
        cohort_merge(dest_cohort=cohort_a, src_cohort=cohort_b)


@pytest.fixture
def collection_with_studies(collection, study_factory):
    study_factory(collection=collection)
    return collection


@pytest.fixture
def collection_with_doi(collection):
    collection.doi = Doi.objects.create(id="10.1000/xyz123", url="https://doi.org/10.1000/xyz123")
    collection.save()
    return collection


@pytest.fixture
def collection_with_shares(collection, user_factory):
    user = user_factory()
    collection.shares.add(user, through_defaults={"creator": collection.creator})
    return collection


@pytest.fixture
def full_collection(collection_factory, image_factory, cohort_factory):
    def _full_collection(public: bool):
        collection = collection_factory(public=public)
        # TODO: difficult to add collection to CohortFactory due to circular dependency
        cohort = cohort_factory()
        cohort.collection = collection
        cohort.save()
        image = image_factory(public=public)
        collection_add_images(collection=collection, image=image)
        return collection

    return _full_collection


@pytest.mark.django_db
def test_merge_collections(full_collection):
    collection_a, collection_b = full_collection(public=True), full_collection(public=True)

    collection_b_pk = collection_b.pk
    collection_b_images = collection_b.images.values_list("pk", flat=True)

    collection_merge_magic_collections(dest_collection=collection_a, src_collection=collection_b)

    collection_a.refresh_from_db()
    assert not Collection.objects.filter(pk=collection_b_pk).exists()
    assert set(collection_b_images) <= set(collection_a.images.values_list("pk", flat=True))


@pytest.mark.django_db
@pytest.mark.parametrize(
    "unmergeable_collection,error",
    [
        [lazy_fixture("collection_with_studies"), "studies"],
        [lazy_fixture("collection_with_doi"), "DOI"],
        [lazy_fixture("collection_with_shares"), "shares"],
    ],
)
def test_merge_collections_unmergeable(collection, unmergeable_collection, error):
    with pytest.raises(ValidationError, match=error):
        collection_merge_magic_collections(
            dest_collection=collection, src_collection=unmergeable_collection
        )


def test_merge_collections_conflicting_fields():
    pass


@pytest.mark.django_db
def test_merge_collections_private_images(collection_factory, image_factory, cohort_factory):
    public_collection = collection_factory(public=True)
    public_collection.cohort = cohort_factory()
    public_collection.cohort.save()
    private_collection = collection_factory(public=False)
    private_collection.cohort = cohort_factory()
    private_collection.cohort.save()
    private_collection.images.add(image_factory(public=False))

    with pytest.raises(ValidationError, match="private"):
        collection_merge_magic_collections(
            dest_collection=public_collection, src_collection=private_collection
        )