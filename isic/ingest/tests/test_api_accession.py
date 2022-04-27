from django.urls.base import reverse
import pytest

from isic.ingest.models.accession import Accession


@pytest.fixture
def accessions(accession_factory, accession_review_factory):
    return [
        accession_review_factory(value=False).accession,
        accession_review_factory(value=False).accession,
        accession_factory(),
        accession_review_factory(value=True).accession,
    ]


@pytest.mark.django_db
def test_api_accession_create(authenticated_api_client, user, cohort_factory, s3ff_field_value):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_api_client.post(
        reverse('accessions:create'), data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )

    assert resp.status_code == 201, resp.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_duplicate_blob_name(
    authenticated_api_client, user, cohort_factory, s3ff_field_value
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_api_client.post(
        reverse('accessions:create'), data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )
    assert resp.status_code == 201, resp.data
    assert cohort.accessions.count() == 1

    resp = authenticated_api_client.post(
        reverse('accessions:create'), data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )
    assert resp.status_code == 400, resp.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_invalid_cohort(
    authenticated_api_client, user_factory, cohort_factory, s3ff_field_value
):
    invalid_cohort = cohort_factory(contributor__creator=user_factory())

    resp = authenticated_api_client.post(
        reverse('accessions:create'),
        data={'cohort': invalid_cohort.pk, 'original_blob': s3ff_field_value},
    )

    assert resp.status_code == 403, resp.data


@pytest.mark.django_db
def test_api_accession_create_review_bulk(staff_api_client, accession_factory):
    accessions = [accession_factory() for _ in range(4)]

    resp = staff_api_client.post(
        reverse('accessions:create-review-bulk'),
        data=[{'id': accession.id, 'value': True} for accession in accessions],
    )

    assert resp.status_code == 201, resp.data
    assert Accession.objects.filter(review=None).count() == 0
