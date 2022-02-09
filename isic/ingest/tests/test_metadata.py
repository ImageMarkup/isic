import csv
import io
from typing import BinaryIO

from django.urls.base import reverse
import pytest

from isic.ingest.tasks import apply_metadata_task
from isic.ingest.tests.csv_streams import StreamWriter
from isic.ingest.utils.metadata import validate_csv_format_and_filenames


@pytest.fixture
def valid_metadatafile(cohort, metadata_file_factory, csv_stream_valid):
    return metadata_file_factory(blob__from_func=lambda: csv_stream_valid, cohort=cohort)


@pytest.fixture
def csv_stream_diagnosis_sex() -> BinaryIO:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=['filename', 'diagnosis', 'sex'])
    writer.writeheader()
    writer.writerow({'filename': 'filename.jpg', 'diagnosis': 'melanoma', 'sex': 'female'})
    return file_stream


@pytest.fixture
def csv_stream_benign() -> BinaryIO:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=['filename', 'benign_malignant'])
    writer.writeheader()
    writer.writerow({'filename': 'filename.jpg', 'benign_malignant': 'benign'})
    return file_stream


@pytest.fixture
def csv_stream_diagnosis_sex_invalid() -> BinaryIO:
    file_stream = StreamWriter(io.BytesIO())
    writer = csv.DictWriter(file_stream, fieldnames=['filename', 'diagnosis', 'sex'])
    writer.writeheader()
    writer.writerow({'filename': 'filename.jpg', 'diagnosis': 'INVALID_DIAGNOSIS', 'sex': 'female'})
    return file_stream


@pytest.fixture
def cohort_with_accession(cohort, accession_factory):
    cohort.accessions.add(accession_factory(cohort=cohort, blob_name='filename.jpg'))
    return cohort


@pytest.mark.django_db
def test_apply_metadata(accession_factory, valid_metadatafile, cohort):
    accession = accession_factory(cohort=cohort, blob_name='filename.jpg')
    apply_metadata_task(valid_metadatafile.pk)
    accession.refresh_from_db()
    assert accession.metadata == {'benign_malignant': 'benign'}
    assert accession.unstructured_metadata == {'foo': 'bar'}


@pytest.fixture
def metadatafile_without_filename_column(
    cohort, metadata_file_factory, csv_stream_without_filename_column
):
    return metadata_file_factory(
        blob__from_func=lambda: csv_stream_without_filename_column, cohort=cohort
    )


@pytest.fixture
def metadatafile_duplicate_filenames(cohort, metadata_file_factory, csv_stream_duplicate_filenames):
    return metadata_file_factory(
        blob__from_func=lambda: csv_stream_duplicate_filenames, cohort=cohort
    )


@pytest.mark.django_db
def test_validate_metadata_step1_requires_filename_column(metadatafile_without_filename_column):
    problems = validate_csv_format_and_filenames(
        metadatafile_without_filename_column.to_df(), metadatafile_without_filename_column.cohort
    )
    assert len(problems) == 1
    assert 'Unable to find a filename column' in problems[0].message


@pytest.mark.django_db
def test_validate_metadata_step1_has_duplicate_filenames(metadatafile_duplicate_filenames):
    problems = validate_csv_format_and_filenames(
        metadatafile_duplicate_filenames.to_df(), metadatafile_duplicate_filenames.cohort
    )
    assert len(problems) == 2
    assert 'Duplicate filenames' in problems[0].message


@pytest.mark.django_db
def test_apply_metadata_step2(
    staff_client, cohort_with_accession, csv_stream_diagnosis_sex, metadata_file_factory
):
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex, cohort=cohort_with_accession
    )

    r = staff_client.post(
        reverse('validate-metadata', args=[cohort_with_accession.pk]),
        {'metadata_file': metadatafile.pk},
    )
    assert not r.context['form'].errors, r.context['form'].errors
    assert r.status_code == 200, r.status_code


@pytest.mark.django_db
def test_apply_metadata_step2_invalid(
    staff_client, cohort_with_accession, csv_stream_diagnosis_sex_invalid, metadata_file_factory
):
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex_invalid, cohort=cohort_with_accession
    )

    r = staff_client.post(
        reverse('validate-metadata', args=[cohort_with_accession.pk]),
        {'metadata_file': metadatafile.pk},
    )
    assert not r.context['form'].errors, r.context['form'].errors
    assert r.status_code == 200, r.status_code
    assert r.context['checkpoint'][1]['problems'] == []
    # Ensure there's an error with the diagnosis field in step 2
    assert r.context['checkpoint'][2]['problems']
    assert list(r.context['checkpoint'][2]['problems'].items())[0][0][0] == 'diagnosis'
    assert r.context['checkpoint'][3]['problems'] == {}


@pytest.mark.django_db
def test_apply_metadata_step3(
    staff_client,
    cohort_with_accession,
    csv_stream_diagnosis_sex,
    csv_stream_benign,
    metadata_file_factory,
):
    # TODO: refactor this test to split out the first half
    metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_diagnosis_sex, cohort=cohort_with_accession
    )

    r = staff_client.post(
        reverse('validate-metadata', args=[cohort_with_accession.pk]),
        {'metadata_file': metadatafile.pk},
    )
    assert not r.context['form'].errors, r.context['form'].errors
    assert r.status_code == 200, r.status_code

    apply_metadata_task(metadatafile.pk)

    # test step 3 by trying to make a melanoma benign
    benign_metadatafile = metadata_file_factory(
        blob__from_func=lambda: csv_stream_benign, cohort=cohort_with_accession
    )

    r = staff_client.post(
        reverse('validate-metadata', args=[cohort_with_accession.pk]),
        {'metadata_file': benign_metadatafile.pk},
    )
    assert not r.context['form'].errors, r.context['form'].errors
    assert r.status_code == 200, r.status_code
    assert r.context['checkpoint'][1]['problems'] == []
    assert r.context['checkpoint'][2]['problems'] == {}
    assert r.context['checkpoint'][3]['problems']
    assert list(r.context['checkpoint'][3]['problems'].items())[0][0][0] == 'diagnosis'
