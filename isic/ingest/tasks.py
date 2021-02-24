import hashlib
import io
from mimetypes import guess_type

import PIL.Image
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import send_mail
from django.db import transaction
import magic
import numpy as np
import pandas as pd

from isic.ingest.models import Accession, DistinctnessMeasure, MetadataFile, Zip
from isic.ingest.validators import MetadataRow
from isic.ingest.zip_utils import files_in_zip, unzip


@shared_task
def extract_zip(zip_id):
    zip = Zip.objects.select_related('creator').get(pk=zip_id)

    with transaction.atomic():
        zip.status = Zip.Status.STARTED
        zip.save(update_fields=['status'])

        blob_names_in_zip = set()
        duplicate_blob_names_in_zip = set()

        for _, original_filename in files_in_zip(zip.blob):
            if original_filename in blob_names_in_zip:
                duplicate_blob_names_in_zip.add(original_filename)
            blob_names_in_zip.add(original_filename)

        blob_name_conflicts = Accession.objects.filter(
            upload__cohort=zip.cohort, blob_name__in=blob_names_in_zip
        ).values_list('blob_name', flat=True)

        if blob_name_conflicts or duplicate_blob_names_in_zip:
            transaction.set_rollback(True)
            send_mail(
                'A problem processing your zip file',
                'The following files must be renamed: '
                + '\n'.join(set(blob_name_conflicts).union(duplicate_blob_names_in_zip)),
                settings.DEFAULT_FROM_EMAIL,
                [zip.creator.email],
            )
            return

        for file_path, original_filename in unzip(zip.blob):
            with open(file_path, 'rb') as original_file_stream:
                blob_size = len(original_file_stream.read())
                original_file_stream.seek(0)

                zip.accessions.create(
                    blob_name=original_filename,
                    # TODO: we're setting blob_size since it's required, but
                    # it actually indicates the stripped blob size, not the original
                    blob_size=blob_size,
                    original_blob=SimpleUploadedFile(
                        original_filename,
                        original_file_stream.read(),
                        guess_type(original_filename)[0],
                    ),
                )
        zip.accessions.update(status=Zip.Status.CREATED)

    # tasks should be delayed after the accessions are committed to the database
    for accession_id in zip.accessions.values_list('id', flat=True):
        process_accession.delay(accession_id)

    zip.status = Zip.Status.COMPLETED
    zip.save(update_fields=['status'])


@shared_task(soft_time_limit=60, time_limit=90)
def process_accession(accession_id):
    accession = Accession.objects.get(pk=accession_id)

    try:
        content = accession.original_blob.open().read()

        if accession.blob_name.startswith('._') or accession.blob_name == 'Thumbs.db':
            # file is probably a macOS resource fork, skip
            accession.status = Accession.Status.SKIPPED
            accession.save(update_fields=['status'])
            return

        m = magic.Magic(mime=True)
        major_mime_type, _ = m.from_buffer(content).split('/')

        if major_mime_type != 'image':
            accession.status = Accession.Status.SKIPPED
            accession.save(update_fields=['status'])
            return

        # determines image is readable, and strips exif tags
        img = PIL.Image.open(io.BytesIO(content))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        accession.blob = SimpleUploadedFile(
            accession.blob_name,
            img_bytes.getvalue(),
            'image/jpeg',
        )
        accession.blob_size = len(img_bytes.getvalue())
        accession.save(update_fields=['blob', 'blob_size'])

        accession.status = Accession.Status.SUCCEEDED
        accession.save(update_fields=['status'])

        process_distinctness_measure.delay(accession.id)
    except SoftTimeLimitExceeded:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        raise
    except Exception:
        accession.status = Accession.Status.FAILED
        accession.save(update_fields=['status'])
        raise


@shared_task(soft_time_limit=60, time_limit=90)
def process_distinctness_measure(accession_id):
    accession = Accession.objects.get(pk=accession_id)

    content = accession.blob.open().read()
    checksum = hashlib.sha256(content).hexdigest()

    DistinctnessMeasure.objects.create(accession=accession, checksum=checksum)


@shared_task
def apply_metadata(metadatafile_id):
    metadata_file = MetadataFile.objects.get(pk=metadatafile_id)
    with metadata_file.blob.open() as csv:
        df = pd.read_csv(csv, header=0)

    # pydantic expects None for the absence of a value, not NaN
    df = df.replace({np.nan: None})

    with transaction.atomic():
        for _, row in df.iterrows():
            accession = Accession.objects.get(
                blob_name=row['filename'], upload__cohort=metadata_file.cohort
            )
            existing_metadata = accession.metadata
            existing_metadata.update(
                MetadataRow.parse_obj(row).dict(exclude_unset=True, exclude_none=True)
            )
            accession.metadata = existing_metadata
            accession.save(update_fields=['metadata'])
