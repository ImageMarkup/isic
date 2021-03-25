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

from isic.ingest.models import Accession, DistinctnessMeasure, MetadataFile, Zip
from isic.ingest.validators import MetadataRow


@shared_task
def extract_zip(zip_id: int):
    zip = Zip.objects.select_related('creator').get(pk=zip_id)
    zip.extract()


@shared_task(soft_time_limit=60, time_limit=90)
def process_accession(accession_id: int):
    accession = Accession.objects.get(pk=accession_id)

    try:
        content = accession.original_blob.open().read()

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
            existing_metadata = accession.metadata
            existing_metadata.update(
                MetadataRow.parse_obj(row).dict(exclude_unset=True, exclude_none=True)
            )
            accession.metadata = existing_metadata
            accession.save(update_fields=['metadata'])
