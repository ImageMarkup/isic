from django.core.exceptions import ValidationError
from django.urls import reverse
import pytest

from isic.ingest.services.cohort import cohort_delete, cohort_relicense


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


@pytest.fixture
def cohort_with_cc_by_accession(cohort_factory, accession_factory, image_factory):
    cohort = cohort_factory(default_copyright_license="CC-BY")
    accession = accession_factory(cohort=cohort, copyright_license="CC-BY")
    accession.save()
    return cohort


@pytest.mark.django_db
def test_cohort_relicense(cohort_with_cc_by_accession):
    cohort_relicense(cohort=cohort_with_cc_by_accession, to_license="CC-0")
    cohort_with_cc_by_accession.refresh_from_db()
    assert cohort_with_cc_by_accession.accessions.first().copyright_license == "CC-0"


@pytest.mark.django_db
def test_cohort_relicense_more_restrictive(cohort_with_cc_by_accession):
    with pytest.raises(ValidationError, match="more restrictive"):
        cohort_relicense(cohort=cohort_with_cc_by_accession, to_license="CC-BY-NC")


@pytest.mark.django_db
def test_cohort_relicense_some_accessions_more_restrictive(
    cohort_with_cc_by_accession, accession_factory
):
    # trying to relicense as CC-BY but an accession is CC-0
    accession = accession_factory(cohort=cohort_with_cc_by_accession, copyright_license="CC-0")
    accession.save()
    with pytest.raises(ValidationError, match="more restrictive"):
        cohort_relicense(cohort=cohort_with_cc_by_accession, to_license="CC-BY")


@pytest.mark.django_db
def test_cohort_list_view(staff_client, cohort, user):
    r = staff_client.get(reverse("cohort-list"))
    assert r.status_code == 200
