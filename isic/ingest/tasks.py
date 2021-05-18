import hashlib
import io

import PIL.Image
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
import magic
import numpy as np
import pandas as pd

from isic.ingest.models import Accession, AccessionStatus, DistinctnessMeasure, MetadataFile, Zip
from isic.ingest.validators import MetadataRow


@shared_task
def extract_zip(zip_pk: int):
    zip = Zip.objects.get(pk=zip_pk)

    try:
        zip.extract_and_notify()
    except Zip.ExtractException:
        # Errors from bad input; these will be logged, but the task is not a failure
        pass
    except SoftTimeLimitExceeded:
        zip.status = Zip.Status.FAILED
        zip.save(update_fields=['status'])
        raise
    else:
        # tasks should be delayed after the accessions are committed to the database
        for accession_id in zip.accessions.values_list('id', flat=True):
            process_accession.delay(accession_id)


@shared_task(soft_time_limit=60, time_limit=90)
def process_accession(accession_id: int):
    accession = Accession.objects.get(pk=accession_id)

    try:
        content = accession.original_blob.open().read()

        m = magic.Magic(mime=True)
        major_mime_type, _ = m.from_buffer(content).split('/')

        if major_mime_type != 'image':
            accession.status = AccessionStatus.SKIPPED
            accession.save(update_fields=['status'])
            return

        # determines image is readable, and strips exif tags
        img = PIL.Image.open(io.BytesIO(content))
        img = img.convert('RGB')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        accession.blob = SimpleUploadedFile(
            accession.blob_name,
            img_bytes.getvalue(),
            'image/jpeg',
        )
        accession.blob_size = len(img_bytes.getvalue())
        accession.height = img.height
        accession.width = img.width
        accession.save(update_fields=['blob', 'blob_size', 'height', 'width'])

        accession.status = AccessionStatus.SUCCEEDED
        accession.save(update_fields=['status'])

        process_distinctness_measure.delay(accession.id)
    except SoftTimeLimitExceeded:
        accession.status = AccessionStatus.FAILED
        accession.save(update_fields=['status'])
        raise
    except Exception:
        accession.status = AccessionStatus.FAILED
        accession.save(update_fields=['status'])
        raise


@shared_task(soft_time_limit=60, time_limit=90)
def process_distinctness_measure(accession_id: int):
    accession = Accession.objects.get(pk=accession_id)

    content = accession.blob.open().read()
    checksum = hashlib.sha256(content).hexdigest()

    DistinctnessMeasure.objects.create(accession=accession, checksum=checksum)


@shared_task
def apply_metadata(metadatafile_id: int):
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
            # filename doesn't need to be stored in the metadata since it's equal to blob_name
            del row['filename']

            metadata = MetadataRow.parse_obj(row)
            accession.unstructured_metadata.update(metadata.unstructured)
            accession.metadata.update(
                metadata.dict(exclude_unset=True, exclude_none=True, exclude={'unstructured'})
            )

            accession.save(update_fields=['metadata', 'unstructured_metadata'])
