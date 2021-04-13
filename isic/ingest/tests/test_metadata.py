import pandas as pd
from pydantic import ValidationError
import pytest

from isic.ingest.util.metadata import get_unstructured_columns, validate_csv_format_and_filenames
from isic.ingest.validators import MetadataRow


def test_melanoma_fields():
    try:
        # mel_class can only be set if diagnosis is melanoma
        MetadataRow(diagnosis='angioma', mel_class='invasive melanoma')
    except ValidationError as e:
        assert len(e.errors()) == 1
        assert e.errors()[0]['loc'][0] == 'mel_class'

    # mel_class can only be set if diagnosis is melanoma
    MetadataRow(diagnosis='melanoma', mel_class='invasive melanoma')


def test_no_benign_melanoma():
    try:
        MetadataRow(diagnosis='melanoma', benign_malignant='benign')
    except ValidationError as e:
        assert len(e.errors()) == 1
        assert e.errors()[0]['loc'][0] == 'diagnosis'


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
