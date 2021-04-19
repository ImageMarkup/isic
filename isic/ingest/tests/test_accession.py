import pytest

from isic.ingest.models import Accession
from isic.ingest.tests.factories import AccessionFactory


@pytest.fixture
def accessions():
    yield [
        AccessionFactory(quality_check=False),
        AccessionFactory(quality_check=False),
        AccessionFactory(quality_check=None),
        AccessionFactory(quality_check=True),
    ]


@pytest.mark.django_db
def test_accession_soft_accept_bulk(accessions, admin_client):
    r = admin_client.patch(
        '/api/v2/accessions/soft_accept_check_bulk/',
        [{'id': x.id, 'checks': ['quality_check']} for x in accessions],
        'application/json',
    )
    assert r.status_code == 200, r.json()

    # The original 2 false quality accessions should remain unchanged
    assert Accession.objects.filter(quality_check=True).count() == 2
    assert Accession.objects.filter(quality_check=False).count() == 2
