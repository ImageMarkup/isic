from collections.abc import Iterable
import time

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import QuerySet
from django.template.loader import render_to_string
from isic_metadata.utils import get_unstructured_columns
from more_itertools.more import chunked

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
from isic.ingest.utils.metadata import (
    ColumnRowErrors,
    Problem,
    validate_archive_consistency,
    validate_csv_format_and_filenames,
    validate_internal_consistency,
)

logger = get_task_logger(__name__)


def throttled_iterator(iterable: Iterable, max_per_second: int = 100) -> Iterable:
    for item in iterable:
        yield item
        time.sleep(1 / max_per_second)


@shared_task(soft_time_limit=60 * 60 * 12, time_limit=60 * 60 * 12 + 30)
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


@shared_task(soft_time_limit=300, time_limit=360)
def validate_metadata_task(metadata_file_pk: int):
    metadata_file = MetadataFile.objects.select_related("cohort").get(pk=metadata_file_pk)

    try:
        df = metadata_file.to_df()
        successful: bool = False
        unstructured_columns: list[str] = get_unstructured_columns(df)
        csv_check: list[Problem] | None = None
        internal_check: tuple[ColumnRowErrors, list[Problem]] | None = None
        archive_check: tuple[ColumnRowErrors, list[Problem]] | None = None

        csv_check = validate_csv_format_and_filenames(df, metadata_file.cohort)

        if not any(csv_check):
            internal_check = validate_internal_consistency(df)

            if not any(internal_check):
                archive_check = validate_archive_consistency(df, metadata_file.cohort)

                if not any(archive_check):
                    successful = True

        metadata_file.validation_errors = render_to_string(
            "ingest/partials/metadata_validation.html",
            {
                "cohort": metadata_file.cohort,  # needs cohort for assembling a redirect url
                "metadata_file_id": metadata_file.pk,
                "successful": successful,
                "unstructured_columns": unstructured_columns,
                "csv_check": csv_check,
                "internal_check": internal_check,
                "archive_check": archive_check,
            },
        )
        metadata_file.validation_completed = True
        metadata_file.save()
    except Exception:
        metadata_file.validation_errors = "An unexpected error occurred during validation."
        metadata_file.validation_completed = True
        metadata_file.save()
        raise


@shared_task(soft_time_limit=3600, time_limit=3600 + 60)
def update_metadata_task(user_pk: int, metadata_file_pk: int):
    metadata_file = MetadataFile.objects.get(pk=metadata_file_pk)
    user = User.objects.get(pk=user_pk)

    with transaction.atomic():
        # Lock the longitudinal tables during metadata assignment
        (_ for _ in Lesion.objects.select_for_update().all())
        (_ for _ in Patient.objects.select_for_update().all())

        rows = metadata_file.to_iterable()
        headers = next(rows)
        filename_index = headers.index("filename")

        for chunk in chunked(rows, 1_000):
            accessions: QuerySet[Accession] = metadata_file.cohort.accessions.select_related(
                "image", "review", "lesion", "patient", "cohort"
            ).filter(original_blob_name__in=[row[filename_index] for row in chunk])
            accessions_by_filename: dict[str, Accession] = {
                accession.original_blob_name: accession for accession in accessions
            }

            for row in chunk:
                # filename doesn't need to be stored in the metadata since it's equal to
                # original_blob_name
                accession = accessions_by_filename[row[filename_index]]
                row = dict(zip(headers, row))
                del row["filename"]
                accession.update_metadata(user, row)


@shared_task(soft_time_limit=3600, time_limit=3660)
def publish_cohort_task(cohort_pk: int, user_pk: int, *, public: bool):
    cohort = Cohort.objects.select_related("collection").get(pk=cohort_pk)
    user = User.objects.get(pk=user_pk)
    cohort_publish(cohort=cohort, publisher=user, public=public)
