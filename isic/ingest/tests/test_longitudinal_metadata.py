import pytest

from isic.ingest.models.accession import Accession


@pytest.fixture()
def imageless_accession(accession_factory):
    return accession_factory(image=None)


@pytest.mark.django_db()
def test_accession_update_patient_metadata(user, accession_factory, cohort):
    accession1 = accession_factory(image=None, cohort=cohort)
    accession2 = accession_factory(image=None, cohort=cohort)

    accession1.update_metadata(user, {"patient_id": "someinternalidentifier"})
    assert accession1.patient.private_patient_id == "someinternalidentifier"

    accession2.update_metadata(user, {"patient_id": "someinternalidentifier"})
    assert accession1.patient.private_patient_id == "someinternalidentifier"

    assert accession1.patient.id == accession2.patient.id


@pytest.mark.django_db()
def test_accession_update_lesion_metadata(user, accession_factory, cohort):
    accession1 = accession_factory(image=None, cohort=cohort)
    accession2 = accession_factory(image=None, cohort=cohort)

    accession1.update_metadata(user, {"lesion_id": "someinternalidentifier"})
    assert accession1.lesion.private_lesion_id == "someinternalidentifier"

    accession2.update_metadata(user, {"lesion_id": "someinternalidentifier"})
    assert accession1.lesion.private_lesion_id == "someinternalidentifier"

    assert accession1.lesion.id == accession2.lesion.id


@pytest.mark.django_db()
def test_accession_update_patient_metadata_idempotent(user, imageless_accession: Accession):
    imageless_accession.update_metadata(user, {"patient_id": "someinternalidentifier"})
    longitudinal_id = imageless_accession.patient.id
    assert imageless_accession.patient.private_patient_id == "someinternalidentifier"
    assert "patient_id" not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(user, {"patient_id": "someinternalidentifier"})
    assert imageless_accession.patient.private_patient_id == "someinternalidentifier"
    assert "patient_id" not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    assert imageless_accession.patient.id == longitudinal_id


@pytest.mark.django_db()
def test_accession_update_lesion_metadata_idempotent(user, imageless_accession: Accession):
    imageless_accession.update_metadata(user, {"lesion_id": "someinternalidentifier"})
    longitudinal_id = imageless_accession.lesion.id
    assert imageless_accession.lesion.private_lesion_id == "someinternalidentifier"
    assert "lesion_id" not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(user, {"lesion_id": "someinternalidentifier"})
    assert imageless_accession.lesion.private_lesion_id == "someinternalidentifier"
    assert "lesion_id" not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    assert imageless_accession.lesion.id == longitudinal_id


@pytest.mark.django_db()
def test_accession_update_patient_metadata_change(user, imageless_accession):
    imageless_accession.update_metadata(user, {"patient_id": "someinternalidentifier"})
    assert imageless_accession.patient.private_patient_id == "someinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(user, {"patient_id": "differentinternalidentifier"})
    assert imageless_accession.patient.private_patient_id == "differentinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 2


@pytest.mark.django_db()
def test_accession_update_lesion_metadata_change(user, imageless_accession):
    imageless_accession.update_metadata(user, {"lesion_id": "someinternalidentifier"})
    assert imageless_accession.lesion.private_lesion_id == "someinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(user, {"lesion_id": "differentinternalidentifier"})
    assert imageless_accession.lesion.private_lesion_id == "differentinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 2
