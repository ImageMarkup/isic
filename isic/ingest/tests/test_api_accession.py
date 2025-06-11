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
def test_api_accession_create(authenticated_client, user, cohort_factory, s3ff_random_field_value):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        "/api/v2/accessions/",
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_creates_accessions_with_unstructured_metadata(
    authenticated_client, user, cohort_factory, s3ff_random_field_value
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        "/api/v2/accessions/",
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1
    assert cohort.accessions.first().unstructured_metadata is not None


@pytest.mark.django_db
def test_api_accession_create_duplicate_blob_name(
    authenticated_client, user, cohort_factory, s3ff_random_field_value
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_client.post(
        "/api/v2/accessions/",
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )
    assert resp.status_code == 201, resp.json()
    assert cohort.accessions.count() == 1

    resp = authenticated_client.post(
        "/api/v2/accessions/",
        data={"cohort": cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )
    assert resp.status_code == 400, resp.json()
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_invalid_cohort(
    authenticated_client, user_factory, cohort_factory, s3ff_random_field_value
):
    invalid_cohort = cohort_factory(contributor__creator=user_factory())

    resp = authenticated_client.post(
        "/api/v2/accessions/",
        data={"cohort": invalid_cohort.pk, "original_blob": s3ff_random_field_value},
        content_type="application/json",
    )

    assert resp.status_code == 403, resp.json()


@pytest.mark.django_db
def test_api_accession_create_review_bulk(staff_client, accession_factory):
    accessions = [accession_factory() for _ in range(4)]

    resp = staff_client.post(
        "/api/v2/accessions/create-review-bulk/",
        data=[{"id": accession.id, "value": True} for accession in accessions],
        content_type="application/json",
    )

    assert resp.status_code == 201, resp.data
    assert Accession.objects.filter(review=None).count() == 0
