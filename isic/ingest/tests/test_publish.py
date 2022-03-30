from django.urls.base import reverse
import pytest

from isic.core.models.image import Image
from isic.ingest.models.accession import AccessionStatus


@pytest.fixture
def publishable_cohort(cohort_factory, accession_factory, user):
    cohort = cohort_factory(creator=user, contributor__creator=user)
    # Make a 'publishable' accession
    accession_factory(
        cohort=cohort,
        status=AccessionStatus.SUCCEEDED,
        blob_size=1,
        width=1,
        height=1,
        quality_check=True,
        diagnosis_check=True,
        phi_check=True,
        duplicate_check=True,
        lesion_check=True,
    )
    accession_factory(cohort=cohort, status=AccessionStatus.SKIPPED)
    return cohort


@pytest.mark.django_db
def test_publish_cohort(staff_client, eager_celery, publishable_cohort):
    staff_client.post(
        reverse('upload/cohort-publish', args=[publishable_cohort.pk]), {'private': True}
    )

    published_images = Image.objects.filter(accession__cohort=publishable_cohort)

    assert published_images.count() == 1
    assert not published_images.first().public
