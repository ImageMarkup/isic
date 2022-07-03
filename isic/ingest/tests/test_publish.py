from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.ingest.models.accession import AccessionStatus


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


@pytest.mark.django_db
def test_publish_cohort(
    staff_client, eager_celery, publishable_cohort, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        staff_client.post(
            reverse('upload/cohort-publish', args=[publishable_cohort.pk]), {'private': True}
        )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort)

    assert published_images.count() == 1
    assert not published_images.first().public
    assert Collection.objects.count() == 1
    magic_collection = Collection.objects.first()
    assert not magic_collection.public
    assert magic_collection.locked
