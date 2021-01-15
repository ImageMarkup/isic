import hashlib
from mimetypes import guess_type
import os
import subprocess

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from girder_utils.files import field_file_to_local_path

from isic.studies.models import Image
from isic.ingest.models import Zip#, UploadBlob, UploadStatus
from isic.ingest.zip_utils import ZipFileOpener


def _strip_exif(field_file) -> bytes:
    with field_file_to_local_path(field_file) as file_path:
        subprocess.check_call(['exiftool', '-All=', file_path])
        return open(file_path, 'rb').read()


@shared_task
def extract_zip(zip_id):
    upload = Zip.objects.get(pk=zip_id)
    upload.status = UploadStatus.STARTED
    upload.save(update_fields=['status'])
    with field_file_to_local_path(upload.blob) as zip_path:
        with ZipFileOpener(zip_path) as (file_list, _):
            for original_file_path, original_file_relpath in file_list:
                original_file_name = os.path.basename(original_file_relpath)
                with open(original_file_path, 'rb') as original_file_stream:
                    upload.blobs.create(
                        blob_name=original_file_name,
                        blob=SimpleUploadedFile(
                            original_file_name,
                            original_file_stream.read(),
                            guess_type(original_file_name),
                        ),
                    )

    for blob_id in upload.blobs.values_list('id', flat=True):
        maybe_upload_blob.delay(blob_id)


@shared_task
def maybe_upload_blob(upload_blob_id):
    """
    Upload a single image from box into the system.

    - Upload a single blob
    - Always attempt to mark the entire upload as complete in case this is the last image
    """

    def maybe_complete_upload(upload: Zip):
        if upload.is_complete:
            upload.last_updated = timezone.now()
            upload.status = UploadStatus.COMPLETED
            upload.save(update_fields=['status', 'last_updated'])

    upload_blob = UploadBlob.objects.get(pk=upload_blob_id)

    import secrets

    objid = secrets.token_hex()[:24]
    try:
        stripped_image = _strip_exif(upload_blob.blob)
        sha = hashlib.sha1(stripped_image).hexdigest()
        # create image record locally
        image = Image.objects.create(
            object_id=objid,
            upload_blob=upload_blob,
            size=upload_blob.blob.blob_size,
            sha1=sha,
        )
        image.blob.save(upload_blob.blob.name, ContentFile(stripped_image))

        upload_blob.succeed()
        maybe_complete_upload(upload_blob.upload)
    except SoftTimeLimitExceeded:
        upload_blob.fail()
        maybe_complete_upload(upload_blob.upload)
        raise
    except Exception as e:
        upload_blob.fail(reason=e)
        maybe_complete_upload(upload_blob.upload)
        raise
