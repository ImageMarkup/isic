import csv
import io
from typing import BinaryIO

from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.ingest.service import accession_review_update_or_create
from isic.ingest.tasks import update_metadata_task
from isic.ingest.tests.csv_streams import StreamWriter
from isic.ingest.utils.metadata import validate_csv_format_and_filenames


@pytest.fixture
def valid_metadatafile(cohort, metadata_file_factory, csv_stream_valid):
    return metadata_file_factory(blob__from_func=lambda: csv_stream_valid, cohort=cohort)


@pytest.fixture
def imageless_accession(accession_factory):
    return accession_factory(image=None)


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
def test_apply_metadata(accession_factory, valid_metadatafile, cohort, user):
    accession = accession_factory(cohort=cohort, blob_name='filename.jpg')
    update_metadata_task(user.pk, valid_metadatafile.pk)
    accession.refresh_from_db()
    assert accession.metadata == {'benign_malignant': 'benign'}
    assert accession.unstructured_metadata == {'foo': 'bar'}
    assert accession.metadata_versions.count() == 1
    version = accession.metadata_versions.first()
    assert version.metadata == {'benign_malignant': 'benign'}
    assert version.unstructured_metadata == {'foo': 'bar'}


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
    user,
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

    update_metadata_task(user.pk, metadatafile.pk)

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


@pytest.mark.django_db
def test_accession_metadata_versions(user, accession):
    accession.update_metadata(user, {'foo': 'bar'})
    assert accession.metadata_versions.count() == 1
    diffs = accession.metadata_versions.differences()
    assert len(diffs) == 1
    assert diffs[0][1] == {
        'unstructured_metadata': {'added': {'foo': 'bar'}, 'removed': {}, 'changed': {}},
        'metadata': {'added': {}, 'removed': {}, 'changed': {}},
    }

    accession.update_metadata(user, {'foo': 'baz', 'age': '45'})
    assert accession.metadata_versions.count() == 2
    diffs = accession.metadata_versions.differences()
    assert len(diffs) == 2
    assert diffs[0][1] == {
        'unstructured_metadata': {'added': {'foo': 'bar'}, 'removed': {}, 'changed': {}},
        'metadata': {'added': {}, 'removed': {}, 'changed': {}},
    }
    assert diffs[1][1] == {
        'unstructured_metadata': {
            'added': {},
            'removed': {},
            'changed': {'foo': {'new_value': 'baz', 'old_value': 'bar'}},
        },
        'metadata': {'added': {'age': 45}, 'removed': {}, 'changed': {}},
    }


@pytest.mark.django_db
def test_accession_metadata_versions_remove(user, imageless_accession):
    imageless_accession.update_metadata(user, {'foo': 'bar', 'baz': 'qux'})
    imageless_accession.remove_metadata(user, ['nonexistent'])
    assert imageless_accession.unstructured_metadata == {'foo': 'bar', 'baz': 'qux'}
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_update_metadata(user, imageless_accession):
    imageless_accession.update_metadata(user, {'sex': 'male', 'foo': 'bar', 'baz': 'qux'})
    assert imageless_accession.unstructured_metadata == {'foo': 'bar', 'baz': 'qux'}
    assert imageless_accession.metadata == {'sex': 'male'}
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_update_metadata_idempotent(user, imageless_accession):
    imageless_accession.update_metadata(user, {'sex': 'male', 'foo': 'bar', 'baz': 'qux'})
    imageless_accession.update_metadata(user, {'sex': 'male', 'foo': 'bar', 'baz': 'qux'})
    # test the case where meta/unstructured are different, but updating wouldn't change anything
    imageless_accession.update_metadata(user, {})
    assert imageless_accession.unstructured_metadata == {'foo': 'bar', 'baz': 'qux'}
    assert imageless_accession.metadata == {'sex': 'male'}
    assert imageless_accession.metadata_versions.count() == 1


@pytest.mark.django_db
def test_accession_remove_metadata(user, imageless_accession):
    imageless_accession.update_metadata(user, {'foo': 'bar', 'baz': 'qux'})
    imageless_accession.remove_metadata(user, ['foo'])
    assert imageless_accession.unstructured_metadata == {'baz': 'qux'}
    assert imageless_accession.metadata_versions.count() == 2


@pytest.mark.django_db
def test_accession_remove_metadata_idempotent(user, imageless_accession):
    imageless_accession.update_metadata(user, {'foo': 'bar', 'baz': 'qux'})
    imageless_accession.remove_metadata(user, ['foo'])
    imageless_accession.remove_metadata(user, ['foo'])
    assert imageless_accession.unstructured_metadata == {'baz': 'qux'}
    assert imageless_accession.metadata_versions.count() == 2


@pytest.fixture
def unpublished_accepted_accession(accession_factory, user):
    accession = accession_factory(image=None)
    accession.update_metadata(user, {'diagnosis': 'melanoma'})
    accession_review_update_or_create(
        accession=accession, reviewer=user, reviewed_at=timezone.now(), value=True
    )
    return accession


@pytest.mark.django_db
def test_update_metadata_resets_checks(user, unpublished_accepted_accession):
    unpublished_accepted_accession.update_metadata(user, {'diagnosis': 'basal cell carcinoma'})
    unpublished_accepted_accession.refresh_from_db()
    assert not unpublished_accepted_accession.reviewed


@pytest.mark.django_db
def test_update_unstructured_metadata_does_not_reset_checks(user, unpublished_accepted_accession):
    unpublished_accepted_accession.update_metadata(user, {'foobar': 'baz'})
    unpublished_accepted_accession.refresh_from_db()
    assert unpublished_accepted_accession.reviewed


@pytest.mark.django_db
def test_remove_metadata_resets_checks(user, unpublished_accepted_accession):
    unpublished_accepted_accession.remove_metadata(user, ['diagnosis'])
    unpublished_accepted_accession.refresh_from_db()
    assert not unpublished_accepted_accession.reviewed
