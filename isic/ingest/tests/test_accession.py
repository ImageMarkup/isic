import pytest

from isic.ingest.models import Accession, CheckLog
from isic.ingest.tests.factories import AccessionFactory


@pytest.fixture
def accessions():
    return [
        AccessionFactory(quality_check=False),
        AccessionFactory(quality_check=False),
        AccessionFactory(quality_check=None),
        AccessionFactory(quality_check=True),
    ]


@pytest.mark.django_db
def test_accession_soft_accept_bulk(accessions, staff_api_client):
    r = staff_api_client.patch(
        '/api/v2/accessions/soft_accept_check_bulk/',
        [{'id': x.id, 'checks': ['quality_check']} for x in accessions],
    )
    assert r.status_code == 200, r.data

    # The original 2 false quality accessions should remain unchanged
    assert Accession.objects.filter(quality_check=True).count() == 2
    assert Accession.objects.filter(quality_check=False).count() == 2


@pytest.mark.django_db
def test_accession_soft_accept_bulk_adds_checklogs(accessions, staff_user, staff_api_client):
    r = staff_api_client.patch(
        '/api/v2/accessions/soft_accept_check_bulk/',
        [{'id': x.id, 'checks': ['quality_check']} for x in accessions],
    )
    assert r.status_code == 200, r.data

    assert CheckLog.objects.count() == 1
    checklog = CheckLog.objects.first()

    assert checklog.accession.pk == accessions[2].pk
    assert checklog.creator.pk == staff_user.pk
    assert checklog.change_field == 'quality_check'
    assert checklog.change_to == True  # noqa: E712


@pytest.mark.django_db
def test_accession_soft_accept_adds_checklogs(staff_user, staff_api_client):
    accession = AccessionFactory(quality_check=None)
    r = staff_api_client.patch(
        f'/api/v2/accessions/{accession.pk}/',
        {'quality_check': False, 'metadata': {}},  # ensure it doesn't care about non-check fields
    )
    assert r.status_code == 200, r.data

    accession.refresh_from_db()
    assert accession.quality_check == False  # noqa: E712

    assert CheckLog.objects.count() == 1
    checklog = CheckLog.objects.first()

    assert checklog.accession.pk == accession.pk
    assert checklog.creator.pk == staff_user.pk
    assert checklog.change_field == 'quality_check'
    assert checklog.change_to == False  # noqa: E712
