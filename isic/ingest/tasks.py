from collections.abc import Iterable
import time

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.contrib.auth.models import User
from django.db import transaction

from isic.ingest.models import (
    Accession,
    AccessionStatus,
    Cohort,
    DistinctnessMeasure,
    Lesion,
    MetadataFile,
    Patient,
    ZipUpload,
)
from isic.ingest.services.cohort import cohort_publish

logger = get_task_logger(__name__)


def throttled_iterator(iterable: Iterable, max_per_second: int = 100) -> Iterable:
    for item in iterable:
        yield item
        time.sleep(1 / max_per_second)


@shared_task(soft_time_limit=7200, time_limit=8100)
def extract_zip_task(zip_pk: int):
    logger.info(f"Extracting zip {zip_pk}.")

    zip_upload = ZipUpload.objects.get(pk=zip_pk)

    try:
        zip_upload.extract_and_notify()
    except ZipUpload.ExtractError:
        # Errors from bad input; these will be logged, but the task is not a failure
        pass
    except SoftTimeLimitExceeded:
        zip_upload.status = ZipUpload.Status.FAILED
        zip_upload.save(update_fields=["status"])
        raise
    else:
        # rmq can only handle ~500msg/s - throttle significantly in places
        # where we could be putting many messages onto the queue at once.
        def generate_blobs():
            for accession_id in throttled_iterator(
                zip_upload.accessions.values_list("id", flat=True).iterator()
            ):
                # avoid .delay since we want to avoid putting tens of thousands of elements
                # into the transaction.on_commit list.
                accession_generate_blob_task.apply_async(args=[accession_id])

        transaction.on_commit(generate_blobs)


@shared_task(soft_time_limit=60, time_limit=90)
def accession_generate_blob_task(accession_pk: int):
    accession = Accession.objects.get(pk=accession_pk)

    try:
        accession.generate_blob()
    except SoftTimeLimitExceeded:
        accession.status = AccessionStatus.FAILED
        accession.save(update_fields=["status"])
        raise

    # Prevent skipped accessions from being passed to this task
    if accession.status == AccessionStatus.SUCCEEDED:
        process_distinctness_measure_task.delay(accession.pk)


@shared_task(soft_time_limit=60, time_limit=90)
def process_distinctness_measure_task(accession_pk: int):
    accession = Accession.objects.get(pk=accession_pk)

    with accession.blob.open() as blob_stream:
        checksum = DistinctnessMeasure.compute_checksum(blob_stream)

    DistinctnessMeasure.objects.create(accession=accession, checksum=checksum)


@shared_task(soft_time_limit=1800, time_limit=1860)
def update_metadata_task(user_pk: int, metadata_file_pk: int):
    metadata_file = MetadataFile.objects.get(pk=metadata_file_pk)
    user = User.objects.get(pk=user_pk)

    with transaction.atomic():
        # Lock the longitudinal tables during metadata assignment
        (_ for _ in Lesion.objects.select_for_update().all())
        (_ for _ in Patient.objects.select_for_update().all())

        # TODO: consider chunking in the future since large CSVs generate a lot of
        # database traffic.
        for _, row in metadata_file.to_df().iterrows():
            accession = Accession.objects.get(
                original_blob_name=row["filename"], cohort=metadata_file.cohort
            )
            # filename doesn't need to be stored in the metadata since it's equal to
            # original_blob_name
            del row["filename"]
            accession.update_metadata(user, row)


@shared_task(soft_time_limit=3600, time_limit=3660)
def publish_cohort_task(cohort_pk: int, user_pk: int, *, public: bool):
    cohort = Cohort.objects.select_related("collection").get(pk=cohort_pk)
    user = User.objects.get(pk=user_pk)
    cohort_publish(cohort=cohort, publisher=user, public=public)
