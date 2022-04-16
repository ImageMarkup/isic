import pytest

from isic.ingest.models import Accession, AccessionReview


@pytest.fixture
def accessions(accession_factory):
    return [
        accession_factory(quality_check=False),
        accession_factory(quality_check=False),
        accession_factory(quality_check=None),
        accession_factory(quality_check=True),
    ]


@pytest.mark.django_db
def test_api_accession_soft_accept_bulk(accessions, staff_api_client):
    r = staff_api_client.patch(
        '/api/v2/accessions/soft_accept_check_bulk/',
        [{'id': x.id, 'checks': ['quality_check']} for x in accessions],
    )
    assert r.status_code == 200, r.data

    # The original 2 false quality accessions should remain unchanged
    assert Accession.objects.filter(quality_check=True).count() == 2
    assert Accession.objects.filter(quality_check=False).count() == 2


@pytest.mark.django_db
def test_api_accession_soft_accept_bulk_adds_checklogs(accessions, staff_user, staff_api_client):
    r = staff_api_client.patch(
        '/api/v2/accessions/soft_accept_check_bulk/',
        [{'id': x.id, 'checks': ['quality_check']} for x in accessions],
    )
    assert r.status_code == 200, r.data

    assert AccessionReview.objects.count() == 1
    checklog = AccessionReview.objects.first()

    assert checklog.accession.pk == accessions[2].pk
    assert checklog.creator.pk == staff_user.pk
    assert checklog.change_field == 'quality_check'
    assert checklog.change_to is True


@pytest.mark.django_db
def test_api_accession_soft_accept_adds_checklogs(accession_factory, staff_user, staff_api_client):
    accession = accession_factory(quality_check=None)
    r = staff_api_client.patch(
        f'/api/v2/accessions/{accession.pk}/',
        {'quality_check': False, 'metadata': {}},  # ensure it doesn't care about non-check fields
    )
    assert r.status_code == 200, r.data

    accession.refresh_from_db()
    assert accession.quality_check is False
    assert accession.review.count() == 1

    assert checklog.accession.pk == accession.pk
    assert checklog.creator.pk == staff_user.pk
    assert checklog.change_field == 'quality_check'
    assert checklog.change_to is False


@pytest.mark.django_db
def test_api_accession_create(authenticated_api_client, user, cohort_factory, s3ff_field_value):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_api_client.post(
        '/api/v2/accessions/', data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )

    assert resp.status_code == 201, resp.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_duplicate_blob_name(
    authenticated_api_client, user, cohort_factory, s3ff_field_value, s3ff_field_value_factory
):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_api_client.post(
        '/api/v2/accessions/', data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )
    assert resp.status_code == 201, resp.data
    assert cohort.accessions.count() == 1

    resp = authenticated_api_client.post(
        '/api/v2/accessions/', data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )
    assert resp.status_code == 400, resp.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_api_accession_create_invalid_cohort(
    authenticated_api_client, user_factory, cohort_factory, s3ff_field_value
):
    invalid_cohort = cohort_factory(contributor__creator=user_factory())

    resp = authenticated_api_client.post(
        '/api/v2/accessions/', data={'cohort': invalid_cohort.pk, 'original_blob': s3ff_field_value}
    )

    assert resp.status_code == 403, resp.data


@pytest.mark.django_db
def test_api_accession_metadata(authenticated_api_client, user, cohort_factory, s3ff_field_value):
    cohort = cohort_factory(contributor__owners=[user])

    resp = authenticated_api_client.post(
        '/api/v2/accessions/', data={'cohort': cohort.pk, 'original_blob': s3ff_field_value}
    )

    assert resp.status_code == 201, resp.data
    assert cohort.accessions.count() == 1
