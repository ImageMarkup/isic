from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from isic.core.models.base import CopyrightLicense
from isic.core.models.collection import Collection
from isic.core.services.collection import collection_merge_magic_collections
from isic.core.services.collection.image import collection_add_images
from isic.core.tests.factories import CollectionFactory, DoiFactory
from isic.factories import UserFactory
from isic.ingest.models.cohort import Cohort
from isic.ingest.services.cohort import cohort_merge
from isic.ingest.services.contributor import contributor_merge
from isic.studies.tests.factories import StudyFactory


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


@pytest.fixture
def contributor_with_cohort(contributor_factory, cohort_factory, user_factory):
    def _contributor_with_cohort():
        user = user_factory()
        contributor = contributor_factory(creator=user, owners=[user])
        contributor.cohorts.add(cohort_factory())
        return contributor

    return _contributor_with_cohort


@pytest.mark.django_db
def test_merge_contributors(contributor_with_cohort):
    contributor_a, contributor_b = contributor_with_cohort(), contributor_with_cohort()

    # make sure that the cohorts/owners from contributor_b are transferred to contributor_a.
    contributor_b_pk = contributor_b.pk
    contributor_b_cohorts = contributor_b.cohorts.values_list("pk", flat=True)
    contributor_b_owners = contributor_b.owners.values_list("pk", flat=True)

    contributor_merge(dest_contributor=contributor_a, src_contributor=contributor_b)

    contributor_a.refresh_from_db()
    assert not Cohort.objects.filter(contributor_id=contributor_b_pk).exists()
    assert set(contributor_b_cohorts) <= set(contributor_a.cohorts.values_list("pk", flat=True))
    assert set(contributor_b_owners) <= set(contributor_a.owners.values_list("pk", flat=True))


@pytest.mark.django_db
def test_merge_cohorts(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

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

    dest_cohort.collection.delete()
    dest_cohort.refresh_from_db()

    total_cohort_images = set(src_cohort.collection.images.values_list("pk", flat=True))

    cohort_merge(dest_cohort=dest_cohort, src_cohort=src_cohort)
    dest_cohort.refresh_from_db()
    assert set(dest_cohort.collection.images.values_list("pk", flat=True)) == total_cohort_images


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


@pytest.mark.django_db
def test_merge_cohorts_with_longitudinal_metadata(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    # set up longitudinal metadata
    accession_a, accession_b = cohort_a.accessions.first(), cohort_b.accessions.first()
    accession_a.update_metadata(accession_a.creator, {"patient_id": "foo"}, ignore_image_check=True)
    accession_b.update_metadata(accession_b.creator, {"patient_id": "foo"}, ignore_image_check=True)

    with pytest.raises(ValidationError, match="patients"):
        cohort_merge(dest_cohort=cohort_a, src_cohort=cohort_b)


@pytest.mark.django_db
def test_merge_cohorts_heterogeneous_licenses(full_cohort):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    accession_a, accession_b = cohort_a.accessions.first(), cohort_b.accessions.first()
    accession_a.copyright_license = CopyrightLicense.CC_0
    accession_a.save()
    accession_b.copyright_license = CopyrightLicense.CC_BY
    accession_b.save()

    cohort_merge(dest_cohort=cohort_a, src_cohort=cohort_b)
    cohort_a.refresh_from_db()
    assert cohort_a.accessions.count() == 2
    assert set(cohort_a.accessions.values_list("copyright_license", flat=True)) == {
        CopyrightLicense.CC_0,
        CopyrightLicense.CC_BY,
    }


@pytest.mark.django_db
def test_merge_cohorts_view(full_cohort, staff_client):
    cohort_a, cohort_b = full_cohort(), full_cohort()

    r = staff_client.post(
        reverse("merge-cohorts"),
        data={"cohort": cohort_a.pk, "cohort_to_merge": cohort_b.pk},
    )
    assert r.status_code == 302
    assert r.url == reverse("cohort-detail", args=[cohort_a.pk])


@pytest.fixture
def full_collection(collection_factory, image_factory, cohort_factory):
    def _full_collection(*, public: bool):
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
def test_merge_collections_unmergeable_doi():
    src_collection = CollectionFactory.create()
    DoiFactory.create(collection=src_collection)
    dest_collection = CollectionFactory.create()

    with pytest.raises(ValidationError, match="DOI"):
        collection_merge_magic_collections(
            dest_collection=dest_collection, src_collection=src_collection
        )


@pytest.mark.django_db
def test_merge_collections_unmergeable_shares():
    src_collection = CollectionFactory.create()
    user = UserFactory.create()
    src_collection.shares.add(user, through_defaults={"grantor": src_collection.creator})
    dest_collection = CollectionFactory.create()

    with pytest.raises(ValidationError, match="shares"):
        collection_merge_magic_collections(
            dest_collection=dest_collection, src_collection=src_collection
        )


@pytest.mark.django_db
def test_merge_collections_unmergeable_study():
    src_collection = CollectionFactory.create()
    StudyFactory.create(collection=src_collection)
    dest_collection = CollectionFactory.create()

    with pytest.raises(ValidationError, match="studies"):
        collection_merge_magic_collections(
            dest_collection=dest_collection, src_collection=src_collection
        )


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
