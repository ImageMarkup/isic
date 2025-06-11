from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from isic.ingest.services.cohort import cohort_delete


@pytest.mark.django_db
def test_cohort_delete(cohort):
    cohort_delete(cohort=cohort)


@pytest.mark.django_db
def test_cohort_delete_with_published_accessions(cohort, accession_factory, image_factory):
    accession = accession_factory(cohort=cohort)
    accession.image = image_factory(accession=accession)
    accession.image.save()

    with pytest.raises(ValidationError):
        cohort_delete(cohort=cohort)


@pytest.mark.django_db
def test_cohort_list_view(staff_client, cohort, user):
    r = staff_client.get(reverse("cohort-list"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_cohort_detail_view_with_published_and_unpublished_accessions(
    staff_client, cohort, accession_factory, image_factory
):
    # there's a lot of shakiness around rendering accessions with both sponsored and non-sponsored
    # images, so this test checks that both work correctly.
    image_factory(accession__cohort=cohort, public=True)
    accession_factory(cohort=cohort, ingested=True)

    r = staff_client.get(reverse("cohort-detail", args=[cohort.pk]))
    assert r.status_code == 200
    assert len(r.context["accessions"]) == 2
