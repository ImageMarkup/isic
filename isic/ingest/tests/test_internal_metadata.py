import pytest

from isic.ingest.models.accession import Accession, RemappedField


@pytest.fixture
def imageless_accession(accession_factory):
    return accession_factory()


@pytest.mark.django_db
@pytest.mark.parametrize("field", Accession.remapped_internal_fields)
def test_accession_update_remapped_metadata(user, accession_factory, cohort, field: RemappedField):
    accession1 = accession_factory(cohort=cohort)
    accession2 = accession_factory(cohort=cohort)

    metadata = {
        field.csv_field_name: "someinternalidentifier",
        # Add the image_type for RCM to avoid validation errors when testing against rcm_case_id
        "image_type": "RCM: tile",
    }

    accession1.update_metadata(user, metadata)
    assert field.internal_value(accession1) == "someinternalidentifier"

    accession2.update_metadata(user, metadata)
    assert field.internal_value(accession2) == "someinternalidentifier"

    assert field.external_value(accession1) == field.external_value(accession2)


@pytest.mark.django_db
@pytest.mark.parametrize("field", Accession.remapped_internal_fields)
def test_accession_update_remapped_metadata_idempotent(
    user, imageless_accession: Accession, field: RemappedField
):
    metadata = {
        field.csv_field_name: "someinternalidentifier",
        # Add the image_type for RCM to avoid validation errors when testing against rcm_case_id
        "image_type": "RCM: macroscopic",
    }
    imageless_accession.update_metadata(user, metadata)
    remapped_id = field.external_value(imageless_accession)
    assert field.internal_value(imageless_accession) == "someinternalidentifier"
    assert field.csv_field_name not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(user, metadata)
    assert field.internal_value(imageless_accession) == "someinternalidentifier"
    assert field.csv_field_name not in imageless_accession.metadata
    assert imageless_accession.metadata_versions.count() == 1

    assert field.external_value(imageless_accession) == remapped_id


@pytest.mark.django_db
@pytest.mark.parametrize("field", Accession.remapped_internal_fields)
def test_accession_update_remapped_metadata_change(user, imageless_accession, field: RemappedField):
    imageless_accession.update_metadata(
        user,
        {
            field.csv_field_name: "someinternalidentifier",
            "image_type": "RCM: macroscopic",
        },
    )
    assert field.internal_value(imageless_accession) == "someinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 1

    imageless_accession.update_metadata(
        user,
        {
            field.csv_field_name: "differentinternalidentifier",
            "image_type": "RCM: macroscopic",
        },
    )
    assert field.internal_value(imageless_accession) == "differentinternalidentifier"
    assert imageless_accession.metadata_versions.count() == 2
