from collections.abc import Generator, Iterable
import itertools
import time

from cachalot.api import cachalot_disabled
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.contrib.auth.models import User
from django.db import transaction
from django.template.loader import render_to_string
from isic_metadata.utils import get_unstructured_columns

from isic.ingest.models import (
    Accession,
    AccessionStatus,
    Cohort,
    DistinctnessMeasure,
    MetadataFile,
    ZipUpload,
    ZipUploadFailReason,
    ZipUploadStatus,
)
from isic.ingest.services.accession import bulk_accession_update_metadata
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
    logger.info("Extracting zip %s.", zip_pk)

    zip_upload = ZipUpload.objects.get(pk=zip_pk)

    try:
        zip_upload.extract_and_notify()
    except ZipUpload.ExtractError:
        # Errors from bad input; these will be logged, but the task is not a failure
        pass
    except SoftTimeLimitExceeded:
        zip_upload.status = ZipUploadStatus.FAILED
        zip_upload.fail_reason = ZipUploadFailReason.OTHER
        zip_upload.save(update_fields=["status", "fail_reason"])
        raise
    else:
        # rmq can only handle ~500msg/s - throttle significantly in places
        # where we could be putting many messages onto the queue at once.
        def generate_blobs():
            with cachalot_disabled():
                for accession_id in throttled_iterator(
                    zip_upload.accessions.values_list("id", flat=True).iterator()
                ):
                    # avoid .delay since we want to avoid putting tens of thousands of elements
                    # into the transaction.on_commit list.
                    accession_generate_blob_task.apply_async(args=[accession_id])

        transaction.on_commit(generate_blobs)


@shared_task(soft_time_limit=300, time_limit=360)
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
        process_distinctness_measure_task.delay_on_commit(accession.pk)


@shared_task(soft_time_limit=60, time_limit=90)
def process_distinctness_measure_task(accession_pk: int):
    accession = Accession.objects.get(pk=accession_pk)

    with accession.blob.open() as blob_stream:
        checksum = DistinctnessMeasure.compute_checksum(blob_stream)

    DistinctnessMeasure.objects.create(accession=accession, checksum=checksum)


@shared_task(soft_time_limit=3600 * 2, time_limit=(3600 * 2) + 60)
def validate_metadata_task(metadata_file_pk: int):
    metadata_file = MetadataFile.objects.select_related("cohort").get(pk=metadata_file_pk)

    try:
        with metadata_file.blob.open("rb") as fh:
            reader = MetadataFile.to_dict_reader(fh)
            successful: bool = False
            unstructured_columns: list[str] = get_unstructured_columns(reader.fieldnames)
            csv_check: list[Problem] | None = None
            internal_check: tuple[ColumnRowErrors, list[Problem]] | None = None
            archive_check: tuple[ColumnRowErrors, list[Problem]] | None = None

            csv_check = validate_csv_format_and_filenames(reader, metadata_file.cohort)

            if not any(csv_check):
                fh.seek(0)
                internal_check = validate_internal_consistency(MetadataFile.to_dict_reader(fh))

                if not any(internal_check):
                    fh.seek(0)
                    archive_check = validate_archive_consistency(
                        MetadataFile.to_dict_reader(fh), metadata_file.cohort
                    )

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


@shared_task(soft_time_limit=3600 * 6, time_limit=(3600 * 6) + 60)
def update_metadata_task(user_pk: int, metadata_file_pk: int):
    metadata_file = MetadataFile.objects.get(pk=metadata_file_pk)
    user = User.objects.get(pk=user_pk)

    def id_metadata_mapping() -> Generator[tuple[int, dict[str, str]], None, None]:
        with metadata_file.blob.open("rb") as blob:
            rows = MetadataFile.to_dict_reader(blob)

            for batch in itertools.batched(rows, 1_000):
                accession_id_by_filename = dict(
                    metadata_file.cohort.accessions.filter(
                        original_blob_name__in=[row["filename"] for row in batch]
                    ).values_list("original_blob_name", "id")
                )

                for row in batch:
                    # filename doesn't need to be stored in the metadata since it's equal to
                    # original_blob_name
                    accession_id = accession_id_by_filename[row["filename"]]
                    del row["filename"]

                    yield accession_id, row

    bulk_accession_update_metadata(
        user=user, metadata=id_metadata_mapping(), metadata_file_id=metadata_file.pk
    )


@shared_task(soft_time_limit=3600, time_limit=3660)
def publish_cohort_task(
    cohort_pk: int, user_pk: int, *, public: bool, collection_ids: list[int] | None = None
):
    cohort = Cohort.objects.select_related("collection").get(pk=cohort_pk)
    user = User.objects.get(pk=user_pk)
    cohort_publish(cohort=cohort, publisher=user, public=public, collection_ids=collection_ids)
