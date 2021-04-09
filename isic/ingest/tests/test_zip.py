# from isic.ingest.models import Zip
import io

import pytest
import requests

from isic.ingest.models import Accession, Zip


@pytest.fixture(params=[b'', b'corrupt_zip'], ids=['empty', 'corrupt'])
def invalid_zip(request, zip_factory):
    return zip_factory(blob__from_func=lambda: io.BytesIO(request.param))


@pytest.fixture
def preexisting_zip(zip, accession_factory):
    # "ISIC_0000001.jpg" is in the zip too
    accession_factory(upload=zip, blob_name='ISIC_0000001.jpg')
    return zip


@pytest.fixture
def duplicates_zip(zip_factory, zip_stream_duplicates):
    return zip_factory(blob__from_func=lambda: zip_stream_duplicates)


@pytest.fixture
def preexisting_and_duplicates_zip(duplicates_zip, accession_factory):
    # "ISIC_0000001.jpg" is in the zip too
    accession_factory(upload=duplicates_zip, blob_name='ISIC_0000001.jpg')
    return duplicates_zip


@pytest.mark.django_db
def test_zip_get_preexisting_and_duplicates_none(zip):
    blob_name_preexisting, blob_name_duplicates = zip._get_preexisting_and_duplicates()

    assert blob_name_preexisting == []
    assert blob_name_duplicates == []


@pytest.mark.django_db
def test_zip_get_preexisting_and_duplicates_preexisting(preexisting_zip):
    blob_name_preexisting, blob_name_duplicates = preexisting_zip._get_preexisting_and_duplicates()

    assert blob_name_preexisting == ['ISIC_0000001.jpg']
    assert blob_name_duplicates == []


@pytest.mark.django_db
def test_zip_get_preexisting_and_duplicates_duplicates(duplicates_zip):
    blob_name_preexisting, blob_name_duplicates = duplicates_zip._get_preexisting_and_duplicates()

    assert blob_name_preexisting == []
    assert blob_name_duplicates == ['ISIC_0000000.jpg', 'ISIC_0000002.jpg']


@pytest.mark.django_db
def test_zip_extract_success(zip):
    zip.extract()

    zip.refresh_from_db()
    assert zip.status == Zip.Status.EXTRACTED
    assert Accession.objects.count() == 5


@pytest.mark.django_db
def test_zip_extract_success_accession_status(zip):
    zip.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    assert accession.status == Accession.Status.CREATED


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_content(zip):
    zip.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    with accession.original_blob.open('rb') as original_blob_stream:
        original_blob_content = original_blob_stream.read()
        # JFIF files start with FF D8 and end with FF D9
        assert original_blob_content.startswith(b'\xff\xd8')
        assert original_blob_content.endswith(b'\xff\xd9')


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_content_type(zip):
    # Ensure that when an accession's original_blob is created, its content type is stored
    zip.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    original_blob_url = accession.original_blob.url
    original_blob_content_type = requests.get(original_blob_url).headers.get('Content-Type')
    assert original_blob_content_type == 'image/jpeg'


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_size(zip):
    # Ensure that when an accession's original_blob is created, its size is stored
    zip.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    assert accession.original_blob.size == 49982


@pytest.mark.django_db
def test_zip_extract_invalid(caplog, invalid_zip):
    with pytest.raises(Zip.InvalidExtractException):
        invalid_zip.extract()

    assert any('Failed zip extraction' in message for message in caplog.messages)
    invalid_zip.refresh_from_db()
    assert invalid_zip.status == Zip.Status.FAILED
    assert Accession.objects.count() == 0


@pytest.mark.django_db
def test_zip_extract_duplicate(caplog, preexisting_and_duplicates_zip):
    with pytest.raises(Zip.DuplicateExtractException):
        preexisting_and_duplicates_zip.extract()

    assert any('Failed zip extraction' in message for message in caplog.messages)
    preexisting_and_duplicates_zip.refresh_from_db()
    assert preexisting_and_duplicates_zip.status == Zip.Status.FAILED
    # preexisting_and_duplicates_zip saves 1 accession
    assert Accession.objects.count() == 1


@pytest.mark.django_db
def test_zip_extract_and_notify_success(mailoutbox, zip):
    zip.extract_and_notify()

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == 'Zip file extracted'
    assert 'successfully received' in mailoutbox[0].body
    assert zip.creator.email in mailoutbox[0].to


@pytest.mark.django_db
def test_zip_extract_and_notify_invalid(mailoutbox, invalid_zip):
    with pytest.raises(Zip.InvalidExtractException):
        invalid_zip.extract_and_notify()

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == 'A problem processing your zip file'
    assert 'corrupt' in mailoutbox[0].body
    assert invalid_zip.creator.email in mailoutbox[0].to


@pytest.mark.django_db
def test_zip_extract_and_notify_duplicate(mailoutbox, preexisting_and_duplicates_zip):
    with pytest.raises(Zip.DuplicateExtractException):
        preexisting_and_duplicates_zip.extract_and_notify()

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == 'A problem processing your zip file'
    # This is preexisting
    assert 'ISIC_0000001' in mailoutbox[0].body
    # These are duplicates
    assert 'ISIC_0000000' in mailoutbox[0].body
    assert 'ISIC_0000002' in mailoutbox[0].body
    assert preexisting_and_duplicates_zip.creator.email in mailoutbox[0].to


@pytest.mark.django_db
def test_zip_reset(zip):
    zip.extract()

    zip.reset()

    zip.refresh_from_db()
    assert zip.status == Zip.Status.CREATED
    assert Accession.objects.count() == 0