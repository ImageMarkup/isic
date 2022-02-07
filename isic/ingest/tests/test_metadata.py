from isic_metadata.utils import get_unstructured_columns
import pandas as pd
import pytest

from isic.ingest.tasks import apply_metadata_task
from isic.ingest.utils.metadata import validate_csv_format_and_filenames


@pytest.fixture
def valid_metadatafile(cohort, metadata_file_factory, csv_stream_valid):
    return metadata_file_factory(blob__from_func=lambda: csv_stream_valid, cohort=cohort)


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


def test_get_unstructured_columns():
    data = [{'age': 25, 'foo': 'bar'}, {'age': 25}, {'age': 25, 'foo': 'bar'}]

    df = pd.DataFrame.from_records(data)

    assert get_unstructured_columns(df) == ['foo']


def test_get_unstructured_columns_ignore_filename():
    data = [{'age': 25, 'foo': 'bar', 'filename': 'foobar'}, {'age': 25}, {'age': 25, 'foo': 'bar'}]

    df = pd.DataFrame.from_records(data)

    assert get_unstructured_columns(df) == ['foo']
