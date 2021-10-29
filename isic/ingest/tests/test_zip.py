import io

import pytest
import requests

from isic.ingest.models import Accession, AccessionStatus, ZipUpload


@pytest.fixture(params=[b'', b'corrupt_zip'], ids=['empty', 'corrupt'])
def invalid_zip(request, zip_upload_factory):
    return zip_upload_factory(blob__from_func=lambda: io.BytesIO(request.param))


@pytest.fixture
def preexisting_zip(zip_upload, accession_factory):
    # "ISIC_0000001.jpg" is in the zip too
    accession_factory(zip_upload=zip_upload, blob_name='ISIC_0000001.jpg')
    return zip_upload


@pytest.fixture
def duplicates_zip(zip_upload_factory, zip_stream_duplicates):
    return zip_upload_factory(blob__from_func=lambda: zip_stream_duplicates)


@pytest.fixture
def preexisting_and_duplicates_zip(duplicates_zip, accession_factory):
    # "ISIC_0000001.jpg" is in the zip too
    accession_factory(zip_upload=duplicates_zip, blob_name='ISIC_0000001.jpg')
    return duplicates_zip


@pytest.mark.django_db
def test_zip_get_preexisting_and_duplicates_none(zip_upload):
    blob_name_preexisting, blob_name_duplicates = zip_upload._get_preexisting_and_duplicates()

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
def test_zip_extract_success(zip_upload):
    zip_upload.extract()

    zip_upload.refresh_from_db()
    assert zip_upload.status == ZipUpload.Status.EXTRACTED
    assert Accession.objects.count() == 5


@pytest.mark.django_db
def test_zip_extract_success_accession_status(zip_upload):
    zip_upload.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    assert accession.status == AccessionStatus.CREATED


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_content(zip_upload):
    zip_upload.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    with accession.original_blob.open('rb') as original_blob_stream:
        original_blob_content = original_blob_stream.read()
        # JFIF files start with FF D8 and end with FF D9
        assert original_blob_content.startswith(b'\xff\xd8')
        assert original_blob_content.endswith(b'\xff\xd9')


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_content_type(zip_upload):
    # Ensure that when an accession's original_blob is created, its content type is stored
    zip_upload.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    original_blob_url = accession.original_blob.url
    original_blob_content_type = requests.get(original_blob_url).headers.get('Content-Type')
    assert original_blob_content_type == 'image/jpeg'


@pytest.mark.django_db
def test_zip_extract_success_accession_original_blob_size(zip_upload):
    # Ensure that when an accession's original_blob is created, its size is stored
    zip_upload.extract()

    accession = Accession.objects.get(blob_name='ISIC_0000000.jpg')
    assert accession.original_blob.size == 49982


@pytest.mark.django_db
def test_zip_extract_invalid(caplog, invalid_zip):
    with pytest.raises(ZipUpload.InvalidExtractError):
        invalid_zip.extract()

    message = next((msg for msg in caplog.messages if 'Failed zip extraction' in msg), None)
    assert message
    assert 'invalid zip' in message
    assert 'File is not a zip file' in message
    invalid_zip.refresh_from_db()
    assert invalid_zip.status == ZipUpload.Status.FAILED
    assert Accession.objects.count() == 0


@pytest.mark.django_db
def test_zip_extract_duplicate(caplog, preexisting_and_duplicates_zip):
    with pytest.raises(ZipUpload.DuplicateExtractError):
        preexisting_and_duplicates_zip.extract()

    message = next((msg for msg in caplog.messages if 'Failed zip extraction' in msg), None)
    assert message
    assert 'duplicates' in message
    preexisting_and_duplicates_zip.refresh_from_db()
    assert preexisting_and_duplicates_zip.status == ZipUpload.Status.FAILED
    # preexisting_and_duplicates_zip saves 1 accession
    assert Accession.objects.count() == 1


@pytest.mark.django_db
def test_zip_extract_and_notify_success(mailoutbox, zip_upload):
    zip_upload.extract_and_notify()

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == 'Zip file extracted'
    assert 'successfully received' in mailoutbox[0].body
    assert zip_upload.creator.email in mailoutbox[0].to


@pytest.mark.django_db
def test_zip_extract_and_notify_invalid(mailoutbox, invalid_zip):
    with pytest.raises(ZipUpload.InvalidExtractError):
        invalid_zip.extract_and_notify()

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == 'A problem processing your zip file'
    assert 'corrupt' in mailoutbox[0].body
    assert invalid_zip.creator.email in mailoutbox[0].to


@pytest.mark.django_db
def test_zip_extract_and_notify_duplicate(mailoutbox, preexisting_and_duplicates_zip):
    with pytest.raises(ZipUpload.DuplicateExtractError):
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
def test_zip_reset(zip_upload):
    zip_upload.extract()

    zip_upload.reset()

    zip_upload.refresh_from_db()
    assert zip_upload.status == ZipUpload.Status.CREATED
    assert Accession.objects.count() == 0
