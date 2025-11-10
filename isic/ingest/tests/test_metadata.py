import codecs
import csv
from decimal import Decimal
import io
from typing import cast

from django.contrib.auth.models import User
from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.ingest.models.accession import Accession, Cohort
from isic.ingest.models.metadata_file import MetadataFile
from isic.ingest.services.accession import bulk_accession_update_metadata
from isic.ingest.services.accession.review import accession_review_update_or_create
from isic.ingest.tasks import update_metadata_task
from isic.ingest.tests.csv_streams import StreamWriter
from isic.ingest.utils.metadata import (
    validate_csv_format_and_filenames,
    validate_internal_consistency,
)
from isic.ingest.views.metadata import ApplyMetadataContext


@pytest.fixture
def valid_metadatafile(cohort, metadata_file_factory, csv_stream_valid):
    return metadata_file_factory(blob__from_func=lambda: csv_stream_valid, cohort=cohort)


@pytest.fixture
def imageless_accession(accession_factory):
    return accession_factory()


@pytest.fixture
def csv_stream_diagnosis_sex() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["filename", "diagnosis", "sex"])
    writer.writeheader()
    writer.writerow({"filename": "filename.jpg", "diagnosis": "Melanoma Invasive", "sex": "female"})
    return file_stream


@pytest.fixture
def csv_stream_diagnosis_sex_lesion_patient() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(
        file_stream,
        fieldnames=["filename", "diagnosis", "sex", "lesion_id", "patient_id"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "filename": "filename.jpg",
            "diagnosis": "Melanoma Invasive",
            "sex": "female",
            "lesion_id": "lesion1",
            "patient_id": "patient1",
        }
    )
    return file_stream


@pytest.fixture
def csv_stream_diagnosis_sex_disagreeing_lesion_patient() -> codecs.StreamWriter:
    # a version that maps the same lesion to a different patient
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(
        file_stream,
        fieldnames=["filename", "diagnosis", "sex", "lesion_id", "patient_id"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "filename": "filename2.jpg",
            "diagnosis": "Melanoma Invasive",
            "sex": "male",
            "lesion_id": "lesion1",
            "patient_id": "patient2",
        }
    )
    return file_stream


@pytest.fixture
def csv_stream_benign() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(
        file_stream,
        fieldnames=["filename", "diagnosis", "anatom_site_general"],
    )
    writer.writeheader()
    writer.writerow(
        {
            "filename": "filename.jpg",
            "diagnosis": "Benign",
            "anatom_site_general": "lower extremity",
        }
    )
    return file_stream


@pytest.fixture
def csv_stream_fingernail() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["filename", "anatom_site_special"])
    writer.writeheader()
    writer.writerow({"filename": "filename.jpg", "anatom_site_special": "fingernail"})
    return file_stream


@pytest.fixture
def csv_stream_diagnosis_sex_invalid() -> codecs.StreamWriter:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=["filename", "diagnosis", "sex"])
    writer.writeheader()
    writer.writerow({"filename": "filename.jpg", "diagnosis": "INVALID_DIAGNOSIS", "sex": "female"})
    return file_stream


@pytest.fixture
def cohort_with_accession(cohort, accession_factory):
    cohort.accessions.add(accession_factory(cohort=cohort, original_blob_name="filename.jpg"))
    cohort.accessions.add(accession_factory(cohort=cohort, original_blob_name="filename2.jpg"))
    return cohort


@pytest.mark.django_db
def test_apply_metadata(accession_factory, valid_metadatafile, cohort, user) -> None:
    accession = accession_factory(cohort=cohort, original_blob_name="filename.jpg")
    update_metadata_task(user.pk, valid_metadatafile.pk)
    accession.refresh_from_db()
    assert accession.metadata == {"diagnosis_1": "Benign"}
    assert accession.unstructured_metadata.value == {"foo": "bar"}
    assert accession.metadata_versions.count() == 1
    version = accession.metadata_versions.first()
    assert version.metadata == {"diagnosis_1": "Benign"}
    assert version.unstructured_metadata == {"foo": "bar"}


@pytest.fixture
def metadatafile_without_filename_column(
    cohort, metadata_file_factory, csv_stream_without_filename_column
):
    return metadata_file_factory(
        blob__from_func=lambda: csv_stream_without_filename_column, cohort=cohort
    )


@pytest.fixture
def metadatafile_bom_filename_column(cohort, metadata_file_factory, csv_stream_bom_filename_column):
    return metadata_file_factory(
        blob__from_func=lambda: csv_stream_bom_filename_column, cohort=cohort
    )


@pytest.fixture
def metadatafile_duplicate_filenames(cohort, metadata_file_factory, csv_stream_duplicate_filenames):
    return metadata_file_factory(
        blob__from_func=lambda: csv_stream_duplicate_filenames, cohort=cohort
    )


@pytest.mark.django_db
def test_valid_batch_invalid_row() -> None:
    bad_batch = [
        {
            "image_type": "dermoscopy",  # error, should be 'dermoscopic'
            "dermoscopic_type": "contact polarized",
            # a field like patient_id is necessary to trigger batch checks
            "patient_id": "12345",
        }
    ]
    errors, batch_errors = validate_internal_consistency(bad_batch)
    assert errors, errors
    assert not batch_errors, batch_errors


@pytest.mark.django_db
def test_validate_metadata_step1_ignores_bom(metadatafile_bom_filename_column) -> None:
    with metadatafile_bom_filename_column.blob.open("rb") as f:
        problems = validate_csv_format_and_filenames(
            MetadataFile.to_dict_reader(f),
            metadatafile_bom_filename_column.cohort,
        )
    assert not problems


@pytest.mark.django_db
def test_validate_metadata_step1_requires_filename_column(
    metadatafile_without_filename_column,
) -> None:
    with metadatafile_without_filename_column.blob.open("rb") as f:
        problems = validate_csv_format_and_filenames(
            MetadataFile.to_dict_reader(f),
            metadatafile_without_filename_column.cohort,
        )
    assert len(problems) == 1
    assert "Unable to find a filename column" in problems[0].message


@pytest.mark.django_db
def test_validate_metadata_step1_has_duplicate_filenames(
    metadatafile_duplicate_filenames,
) -> None:
    with metadatafile_duplicate_filenames.blob.open("rb") as f:
        problems = validate_csv_format_and_filenames(
            MetadataFile.to_dict_reader(f),
            metadatafile_duplicate_filenames.cohort,
        )
    assert len(problems) == 2
    assert "Duplicate filenames" in problems[0].message


@pytest.mark.django_db
def test_apply_metadata_step2(
    staff_client, cohort_with_accession, csv_stream_diagnosis_sex, metadata_file_factory
) -> None:
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex, cohort=cohort_with_accession
    )

    r = staff_client.post(
        reverse("validate-metadata", args=[cohort_with_accession.pk]),
        {"metadata_file": metadatafile.pk},
    )

    assert r.status_code == 302, r.status_code


@pytest.mark.django_db
def test_apply_metadata_step2_invalid(
    staff_client,
    cohort_with_accession,
    csv_stream_diagnosis_sex_invalid,
    metadata_file_factory,
    mocker,
    django_capture_on_commit_callbacks,
) -> None:
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex_invalid,
        cohort=cohort_with_accession,
    )

    import isic.ingest.tasks

    render_to_string = mocker.spy(isic.ingest.tasks, "render_to_string")

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("validate-metadata", args=[cohort_with_accession.pk]),
            {"metadata_file": metadatafile.pk},
            follow=True,
        )
    r.context = cast(ApplyMetadataContext, r.context)
    assert r.status_code == 200, r.status_code
    assert render_to_string.call_args[0][1]["successful"] is False
    assert render_to_string.call_args[0][1]["csv_check"] == []
    assert render_to_string.call_args[0][1]["internal_check"]
    assert (
        next(iter(render_to_string.call_args[0][1]["internal_check"][0].keys()))[0] == "diagnosis"
    )
    assert render_to_string.call_args[0][1]["archive_check"] is None


@pytest.mark.django_db
def test_apply_metadata_step3_full_cohort(
    user,
    staff_client,
    cohort_with_accession,
    csv_stream_diagnosis_sex_lesion_patient,
    csv_stream_diagnosis_sex_disagreeing_lesion_patient,
    metadata_file_factory,
    mocker,
    django_capture_on_commit_callbacks,
) -> None:
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex_lesion_patient,
        cohort=cohort_with_accession,
    )

    # must use spy here - see above.
    import isic.ingest.tasks

    render_to_string = mocker.spy(isic.ingest.tasks, "render_to_string")

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("validate-metadata", args=[cohort_with_accession.pk]),
            {"metadata_file": metadatafile.pk},
            follow=True,
        )
    assert r.status_code == 200, r.status_code
    assert render_to_string.call_args[0][1]["successful"]

    update_metadata_task(user.pk, metadatafile.pk)
    render_to_string.reset_mock()

    # test step 3 by trying to upload a disagreeing lesion/patient pair.
    disagreeing_metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex_disagreeing_lesion_patient,
        cohort=cohort_with_accession,
    )

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("validate-metadata", args=[cohort_with_accession.pk]),
            {"metadata_file": disagreeing_metadatafile.pk},
            follow=True,
        )
    r.context = cast(ApplyMetadataContext, r.context)
    assert render_to_string.call_args[0][1]["successful"] is False
    assert render_to_string.call_args[0][1]["csv_check"] == []
    assert render_to_string.call_args[0][1]["internal_check"]
    assert not any(render_to_string.call_args[0][1]["internal_check"])
    assert render_to_string.call_args[0][1]["archive_check"]
    assert "belong to multiple patients" in str(
        render_to_string.call_args[0][1]["archive_check"][1][0].message
    )


@pytest.mark.django_db
def test_accession_metadata_versions(user, accession) -> None:
    accession.update_metadata(user, {"foo": "bar"})
    assert accession.metadata_versions.count() == 1
    diffs = accession.metadata_versions.differences()
    assert len(diffs) == 1
    assert diffs[0][1] == {
        "unstructured_metadata": {
            "added": {"foo": "bar"},
            "removed": {},
            "changed": {},
        },
        "metadata": {"added": {}, "removed": {}, "changed": {}},
        "lesion": {"added": {}, "removed": {}, "changed": {}},
        "patient": {"added": {}, "removed": {}, "changed": {}},
        "rcm_case": {"added": {}, "removed": {}, "changed": {}},
    }

    accession.update_metadata(user, {"foo": "baz", "age": "45"})
    assert accession.metadata_versions.count() == 2
    diffs = accession.metadata_versions.differences()
    assert len(diffs) == 2
    assert diffs[0][1] == {
        "unstructured_metadata": {
            "added": {"foo": "bar"},
            "removed": {},
            "changed": {},
        },
        "metadata": {"added": {}, "removed": {}, "changed": {}},
        "lesion": {"added": {}, "removed": {}, "changed": {}},
        "patient": {"added": {}, "removed": {}, "changed": {}},
        "rcm_case": {"added": {}, "removed": {}, "changed": {}},
    }
    assert diffs[1][1] == {
        "unstructured_metadata": {
            "added": {},
            "removed": {},
            "changed": {"foo": {"new_value": "baz", "old_value": "bar"}},
        },
        "metadata": {"added": {"age": 45}, "removed": {}, "changed": {}},
        "lesion": {"added": {}, "removed": {}, "changed": {}},
        "patient": {"added": {}, "removed": {}, "changed": {}},
        "rcm_case": {"added": {}, "removed": {}, "changed": {}},
    }


@pytest.mark.django_db
def test_accession_metadata_versions_remove(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"foo": "bar", "baz": "qux"})
    imageless_accession.remove_unstructured_metadata(user, ["nonexistent"])
    assert imageless_accession.unstructured_metadata.value == {
        "foo": "bar",
        "baz": "qux",
    }
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_update_metadata(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"sex": "male", "foo": "bar", "baz": "qux"})
    assert imageless_accession.unstructured_metadata.value == {
        "foo": "bar",
        "baz": "qux",
    }
    assert imageless_accession.metadata == {"sex": "male"}
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_update_metadata_iddx(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"diagnosis": "Nevus"})
    assert imageless_accession.metadata == {
        "diagnosis_1": "Benign",
        "diagnosis_2": "Benign melanocytic proliferations",
        "diagnosis_3": "Nevus",
    }
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_update_metadata_idempotent(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"sex": "male", "foo": "bar", "baz": "qux"})
    imageless_accession.update_metadata(user, {"sex": "male", "foo": "bar", "baz": "qux"})
    # test the case where meta/unstructured are different, but updating wouldn't change anything
    imageless_accession.update_metadata(user, {})
    assert imageless_accession.unstructured_metadata.value == {
        "foo": "bar",
        "baz": "qux",
    }
    assert imageless_accession.metadata == {"sex": "male"}
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_remove_unstructured_metadata(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"foo": "bar", "baz": "qux"})
    imageless_accession.remove_unstructured_metadata(user, ["foo"])
    assert imageless_accession.unstructured_metadata.value == {"baz": "qux"}
    assert imageless_accession.metadata_versions.count() == 2


@pytest.mark.django_db
def test_accession_remove_metadata(user, imageless_accession) -> None:
    imageless_accession.update_metadata(
        user, {"diagnosis": "Melanoma Invasive", "family_hx_mm": "true"}
    )
    imageless_accession.remove_metadata(user, ["diagnosis_3"])
    assert imageless_accession.metadata == {
        "diagnosis_1": "Malignant",
        "diagnosis_2": "Malignant melanocytic proliferations (Melanoma)",
        "family_hx_mm": True,
    }
    assert imageless_accession.metadata_versions.count() == 2


@pytest.mark.django_db
def test_accession_remove_metadata_idempotent(user, imageless_accession) -> None:
    imageless_accession.update_metadata(
        user, {"diagnosis": "Melanoma Invasive", "family_hx_mm": "true"}
    )
    imageless_accession.remove_metadata(user, ["diagnosis_3"])
    imageless_accession.remove_metadata(user, ["diagnosis_3"])
    assert imageless_accession.metadata == {
        "diagnosis_1": "Malignant",
        "diagnosis_2": "Malignant melanocytic proliferations (Melanoma)",
        "family_hx_mm": True,
    }
    assert imageless_accession.metadata_versions.count() == 2


@pytest.mark.django_db
def test_accession_remove_unstructured_metadata_idempotent(user, imageless_accession) -> None:
    imageless_accession.update_metadata(user, {"foo": "bar", "baz": "qux"})
    imageless_accession.remove_unstructured_metadata(user, ["foo"])
    imageless_accession.remove_unstructured_metadata(user, ["foo"])
    assert imageless_accession.unstructured_metadata.value == {"baz": "qux"}
    assert imageless_accession.metadata_versions.count() == 2


@pytest.fixture
def unpublished_accepted_accession(accession_factory, user: User):
    accession = accession_factory()
    accession.update_metadata(user, {"sex": "female"})
    accession_review_update_or_create(
        accession=accession, reviewer=user, reviewed_at=timezone.now(), value=True
    )
    return accession


@pytest.mark.django_db
@pytest.mark.parametrize("reset_review", [True, False])
def test_update_metadata_resets_checks(user, unpublished_accepted_accession, reset_review) -> None:
    unpublished_accepted_accession.update_metadata(user, {"sex": "male"}, reset_review=reset_review)
    unpublished_accepted_accession.refresh_from_db()

    if reset_review:
        assert not unpublished_accepted_accession.reviewed
    else:
        assert unpublished_accepted_accession.reviewed


@pytest.mark.django_db
def test_update_unstructured_metadata_does_not_reset_checks(
    user, unpublished_accepted_accession
) -> None:
    unpublished_accepted_accession.update_metadata(user, {"foobar": "baz"})
    unpublished_accepted_accession.refresh_from_db()
    assert unpublished_accepted_accession.reviewed


@pytest.mark.django_db
def test_metadata_version_serializes_decimal(user: User, accession: Accession) -> None:
    accession.update_metadata(user, {"clin_size_long_diam_mm": 5})
    assert accession.clin_size_long_diam_mm == Decimal("5.0")
    assert accession.metadata_versions.count() == 1
    assert accession.metadata_versions.first().metadata == {"clin_size_long_diam_mm": "5"}  # type: ignore[union-attr]


@pytest.mark.django_db
def test_bulk_accession_update_metadata_defers_constraints(
    user: User, cohort: Cohort, accession_factory
) -> None:
    accession_a, accession_b = accession_factory(cohort=cohort), accession_factory(cohort=cohort)
    accession_a.update_metadata(user, {"lesion_id": "lesion_foo", "patient_id": "patient_foo"})
    accession_b.update_metadata(user, {"lesion_id": "lesion_bar", "patient_id": "patient_bar"})

    # it's possible that the constraints are violated
    # during the update, and we want to ensure that the constraints are deferred. an example
    # is that accession_a wants to swap lesion_id with accession_b. in this case, the
    # "identical lesion implies identical patient" constraint will be violated temporarily and
    # raise the exclusion constraint. this verifies that the constraints are deferred until commit
    # time so the error isn't raised as long as the end result is valid.

    bulk_accession_update_metadata(
        user=user,
        metadata=[
            (accession_a.id, {"lesion_id": "lesion_bar"}),
            (accession_b.id, {"lesion_id": "lesion_foo"}),
        ],
    )
