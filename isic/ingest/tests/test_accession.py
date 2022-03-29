import os
import pathlib

from django.core.exceptions import ValidationError
from django.urls.base import reverse
import pytest

from isic.ingest.models.accession import Accession
from isic.ingest.utils.zip import Blob

data_dir = pathlib.Path(__file__).parent / 'data'


@pytest.fixture
def user_with_cohort(user, cohort_factory):
    cohort = cohort_factory(contributor__creator=user)
    return user, cohort


@pytest.fixture
def jpg_blob():
    with open(data_dir / 'ISIC_0000000.jpg', 'rb') as stream:
        yield Blob(
            name='ISIC_0000000.jpg',
            stream=stream,
            size=os.path.getsize(data_dir / 'ISIC_0000000.jpg'),
        )


@pytest.mark.django_db
def test_accession_generate_thumbnail(accession_factory):
    accession = accession_factory(thumbnail_256=None)

    accession.generate_thumbnail()

    with accession.thumbnail_256.open() as thumbnail_stream:
        thumbnail_content = thumbnail_stream.read()
        assert thumbnail_content.startswith(b'\xff\xd8')


@pytest.mark.django_db
def test_accession_without_zip_upload(user, jpg_blob, cohort):
    accession = Accession.from_blob(jpg_blob)
    accession.creator = user
    accession.cohort = cohort
    accession.save()


@pytest.mark.django_db
def test_accession_upload(authenticated_client, s3ff_field_value, user_with_cohort):
    _, cohort = user_with_cohort
    r = authenticated_client.post(
        reverse('upload/single-accession', args=[cohort.pk]),
        {'original_blob': s3ff_field_value},
    )
    assert r.status_code == 302, r.data
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_accession_upload_duplicate_name(authenticated_client, s3ff_field_value, user_with_cohort):
    _, cohort = user_with_cohort
    r = authenticated_client.post(
        reverse('upload/single-accession', args=[cohort.pk]),
        {'original_blob': s3ff_field_value},
    )
    assert r.status_code == 302, r.data
    assert cohort.accessions.count() == 1

    # try uploading the same file
    r = authenticated_client.post(
        reverse('upload/single-accession', args=[cohort.pk]),
        {'original_blob': s3ff_field_value},
    )
    assert r.status_code == 200, r.data
    assert r.context['form'].errors
    assert cohort.accessions.count() == 1


@pytest.mark.django_db
def test_accession_upload_invalid_cohort(
    authenticated_client, s3ff_field_value, cohort_factory, user_factory
):
    # create a cohort owned by someone else to try to upload to
    cohort = cohort_factory(contributor__creator=user_factory())

    r = authenticated_client.get(reverse('upload/single-accession', args=[cohort.pk]))
    assert r.status_code == 403, r.data

    r = authenticated_client.post(
        reverse('upload/single-accession', args=[cohort.pk]),
        {'original_blob': s3ff_field_value},
    )
    assert r.status_code == 403, r.data


@pytest.mark.django_db
def test_accession_mutable_before_publish(user, accession_factory):
    accession = accession_factory(image=None)
    accession.update_metadata(user, {'foo': 'bar'})
    accession.save()


@pytest.mark.django_db
def test_accession_immutable_after_publish(user, image_factory):
    image = image_factory()

    with pytest.raises(ValidationError):
        image.accession.update_metadata(user, {'foo': 'bar'})
        image.accession.save()


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
