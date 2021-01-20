import io
from mimetypes import guess_type
import os

import PIL.Image
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.uploadedfile import SimpleUploadedFile
import magic

from isic.ingest.models import Accession, Zip
from isic.ingest.zip_utils import ZipFileOpener


@shared_task
def extract_zip(zip_id):
    zip = Zip.objects.get(pk=zip_id)

    zip.status = Zip.Status.STARTED
    zip.save(update_fields=['status'])

    with ZipFileOpener(zip.blob) as (file_list, _):
        for original_file_path, original_file_relpath in file_list:
            original_file_name = os.path.basename(original_file_relpath)

            with open(original_file_path, 'rb') as original_file_stream:
                zip.accessions.create(
                    blob_name=original_file_name,
                    blob_size=1,  # TODO: use tell to get size
                    blob=SimpleUploadedFile(
                        original_file_name,
                        original_file_stream.read(),
                        guess_type(original_file_name),
                    ),
                )

    zip.accessions.update(status=Zip.Status.CREATED)

    for accession_id in zip.accessions.values_list('id', flat=True):
        process_accession.delay(accession_id)

    zip.status = Zip.Status.COMPLETED
    zip.save(update_fields=['status'])


@shared_task
def process_accession(accession_id):
    accession = Accession.objects.get(pk=accession_id)

    try:
        content = accession.blob.open().read()

        # TODO: thumbs.db
        if accession.blob_name.startswith('._'):
            # file is probably a macOS resource fork, skip
            accession.status = Accession.Status.SKIPPED
            accession.save(update_fields=['status'])
            return

        m = magic.Magic(mime=True)
        mime_type = m.from_buffer(content)

        if mime_type != 'image/jpeg':
            print(mime_type)
            accession.status = Accession.Status.SKIPPED
            accession.save(update_fields=['status'])
            return

        # TODO: strip exif?

        # done just to determine the image is readable by PIL
        PIL.Image.open(io.BytesIO(content))

        accession.status = Accession.Status.SUCCEEDED
        accession.save(update_fields=['status'])
        # todo: post processing checksum
        # DistinctnessMeasure
    except SoftTimeLimitExceeded:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        raise
    except Exception:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        raise
