from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.ingest.models.accession import AccessionStatus
from isic.ingest.services.cohort import cohort_publish_initialize


@pytest.fixture
def publishable_cohort(cohort_factory, accession_factory, accession_review_factory, user):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    # Make a 'publishable' accession
    accession_review_factory(
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    accession_factory(cohort=cohort, status=AccessionStatus.SKIPPED)
    return cohort


@pytest.fixture
def publishable_cohort_for_attributions(
    cohort_factory, accession_factory, accession_review_factory, user
):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    # Make publishable accessions, one with an attribution, one without
    accession_review_factory(
        accession__attribution="has an attribution",
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    accession_review_factory(
        accession__attribution="",
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=user,
        reviewed_at=timezone.now(),
        value=True,
    )
    return cohort


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_publish_copies_default_attribution(
    publishable_cohort_for_attributions,
    user,
    django_capture_on_commit_callbacks,
):
    assert set(
        publishable_cohort_for_attributions.accessions.values_list("attribution", flat=True)
    ) == {"has an attribution", ""}

    publishable_cohort_for_attributions.default_attribution = "default attribution"
    publishable_cohort_for_attributions.save(update_fields=["default_attribution"])

    with django_capture_on_commit_callbacks(execute=True):
        cohort_publish_initialize(
            cohort=publishable_cohort_for_attributions,
            publisher=user,
            public=True,
        )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort_for_attributions)

    assert published_images.count() == 2
    assert set(published_images.values_list("accession__attribution", flat=True)) == {
        "has an attribution",
        "default attribution",
    }


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_publish_cohort(
    staff_client, publishable_cohort, django_capture_on_commit_callbacks, collection_factory
):
    collection_a = collection_factory(public=False)
    collection_b = collection_factory(public=False)

    with django_capture_on_commit_callbacks(execute=True):
        staff_client.post(
            reverse("upload/cohort-publish", args=[publishable_cohort.pk]),
            {"private": True, "additional_collections": [collection_a.pk, collection_b.pk]},
        )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort)

    assert published_images.count() == 1
    assert not published_images.first().public  # type: ignore[union-attr]
    assert Collection.objects.count() == 3
    publishable_cohort.refresh_from_db()
    magic_collection = publishable_cohort.collection
    assert not magic_collection.public
    assert magic_collection.locked

    for collection in [collection_a, collection_b]:
        assert collection.images.count() == 1


@pytest.mark.django_db
def test_publish_cohort_into_public_collection(
    staff_client, publishable_cohort, django_capture_on_commit_callbacks, collection_factory
):
    public_collection = collection_factory(public=True)

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("upload/cohort-publish", args=[publishable_cohort.pk]),
            {"private": True, "additional_collections": [public_collection.pk]},
        )
        assert (
            "add private images into a public collection" in r.context["form"].errors["__all__"][0]
        )
