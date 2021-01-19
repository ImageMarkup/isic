import hashlib
import io
from mimetypes import guess_type
import os

import PIL.Image
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.uploadedfile import SimpleUploadedFile
from girder_utils.files import field_file_to_local_path

from isic.ingest.models import Accession, Zip
from isic.ingest.zip_utils import ZipFileOpener


@shared_task
def extract_zip(zip_id):
    zip = Zip.objects.get(pk=zip_id)

    with field_file_to_local_path(zip.blob) as zip_path:
        with ZipFileOpener(zip_path) as (file_list, _):
            for original_file_path, original_file_relpath in file_list:
                original_file_name = os.path.basename(original_file_relpath)
                with open(original_file_path, 'rb') as original_file_stream:
                    zip.accessions.create(
                        blob_name=original_file_name,
                        blob_size=1,
                        blob=SimpleUploadedFile(
                            original_file_name,
                            original_file_stream.read(),
                            guess_type(original_file_name),
                        ),
                    )

    zip.status = Zip.Status.STARTED
    zip.save(update_fields=['status'])

    for accession_id in zip.accessions.values_list('id', flat=True):
        process_accession.delay(accession_id)


@shared_task
def process_accession(accession_id):
    def maybe_complete_upload(upload: Zip):
        if upload.is_complete:
            upload.status = Zip.Status.COMPLETED
            upload.save(update_fields=['status'])

    accession = Accession.objects.get(pk=accession_id)

    try:
        sha1 = hashlib.sha1(accession.blob.open().read()).hexdigest()
        accession.sha1 = sha1

        # TODO: strip exif?

        # done just to determine the image is readable by PIL
        PIL.Image.open(io.BytesIO(accession.blob.open().read()))

        accession.status = Accession.Status.SUCCEEDED
        accession.save(update_fields=['status', 'sha1'])
        maybe_complete_upload(accession.upload)
    except SoftTimeLimitExceeded:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        maybe_complete_upload(accession.upload)
        raise
    except Exception:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        maybe_complete_upload(accession.upload)
        raise
