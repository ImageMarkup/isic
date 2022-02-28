import io

import PIL.Image
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from isic.core.models import Image
from isic.core.search import add_to_search_index
from isic.ingest.models import (
    Accession,
    AccessionStatus,
    Cohort,
    DistinctnessMeasure,
    MetadataFile,
    ZipUpload,
)
from isic.ingest.utils.mime import guess_mime_type


@shared_task
def generate_thumbnail_task(accession_pk: int) -> None:
    accession = Accession.objects.get(pk=accession_pk)
    accession.generate_thumbnail()


@shared_task
def extract_zip_task(zip_pk: int):
    zip_upload = ZipUpload.objects.get(pk=zip_pk)

    try:
        zip_upload.extract_and_notify()
    except ZipUpload.ExtractError:
        # Errors from bad input; these will be logged, but the task is not a failure
        pass
    except SoftTimeLimitExceeded:
        zip_upload.status = ZipUpload.Status.FAILED
        zip_upload.save(update_fields=['status'])
        raise
    else:
        # tasks should be delayed after the accessions are committed to the database
        for accession_id in zip_upload.accessions.values_list('id', flat=True):
            process_accession_task.delay(accession_id)


@shared_task(soft_time_limit=60, time_limit=90)
def process_accession_task(accession_pk: int):
    accession = Accession.objects.get(pk=accession_pk)

    try:
        with accession.original_blob.open('rb') as original_blob_stream:
            blob_mime_type = guess_mime_type(original_blob_stream, accession.blob_name)
        blob_major_mime_type = blob_mime_type.partition('/')[0]
        if blob_major_mime_type != 'image':
            accession.status = AccessionStatus.SKIPPED
            accession.save(update_fields=['status'])
            return

        content = accession.original_blob.open().read()

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

        process_distinctness_measure_task.delay(accession.pk)
        generate_thumbnail_task.delay(accession.pk)
    except SoftTimeLimitExceeded:
        accession.status = AccessionStatus.FAILED
        accession.save(update_fields=['status'])
        raise
    except Exception:
        accession.status = AccessionStatus.FAILED
        accession.save(update_fields=['status'])
        raise


@shared_task(soft_time_limit=60, time_limit=90)
def process_distinctness_measure_task(accession_pk: int):
    accession = Accession.objects.get(pk=accession_pk)

    with accession.blob.open() as blob_stream:
        checksum = DistinctnessMeasure.compute_checksum(blob_stream)

    DistinctnessMeasure.objects.create(accession=accession, checksum=checksum)


@shared_task
def apply_metadata_task(metadata_file_pk: int):
    metadata_file = MetadataFile.objects.get(pk=metadata_file_pk)

    with transaction.atomic():
        for _, row in metadata_file.to_df().iterrows():
            accession = Accession.objects.get(
                blob_name=row['filename'], cohort=metadata_file.cohort
            )
            # filename doesn't need to be stored in the metadata since it's equal to blob_name
            del row['filename']
            accession.apply_metadata(row)
            accession.save(update_fields=['metadata', 'unstructured_metadata'])


@shared_task
def publish_accession_task(accession_pk: int, *, public: bool):
    accession = Accession.objects.get(pk=accession_pk)

    image = Image.objects.create(
        accession=accession,
        public=public,
    )

    add_to_search_index(image)


@shared_task
def publish_cohort_task(cohort_pk: int, *, public: bool):
    cohort = Cohort.objects.get(pk=cohort_pk)
    for accession_pk in cohort.publishable_accessions().values_list('pk', flat=True):
        publish_accession_task.delay(accession_pk, public=public)
