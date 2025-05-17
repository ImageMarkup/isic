from collections.abc import Iterable, Mapping
from itertools import batched
from typing import Any

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.db import transaction
from django.db.models import FileField
from django.db.models.query import QuerySet
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.models.base import CopyrightLicense
from isic.core.utils.db import lock_table_for_writes
from isic.ingest.models.accession import Accession
from isic.ingest.models.bulk_metadata_application import BulkMetadataApplication
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.lesion import Lesion
from isic.ingest.models.patient import Patient
from isic.ingest.models.rcm_case import RcmCase
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata


# Note: this method isn't used when creating accessions as part of a zip extraction.
def accession_create(
    *,
    creator: User,
    cohort: Cohort,
    original_blob: File | str,
    original_blob_name: str,
    original_blob_size: int,
) -> Accession:
    from isic.ingest.tasks import accession_generate_blob_task

    # TODO: should the user this is acting on behalf of be the same as the creator?
    if not creator.has_perm("ingest.add_accession", cohort):
        raise ValidationError("You do not have permission to add an image to this cohort.")

    if cohort.accessions.filter(original_blob_name=original_blob_name).exists():
        raise ValidationError("An accession with this name already exists.")

    if isinstance(original_blob, S3PlaceholderFile):
        original_blob = original_blob.name

    with transaction.atomic():
        accession = Accession(
            creator=creator,
            cohort=cohort,
            copyright_license=cohort.default_copyright_license,
            original_blob=original_blob,
            original_blob_name=original_blob_name,
            original_blob_size=original_blob_size,
        )
        accession.unstructured_metadata = UnstructuredMetadata(accession=accession)
        accession.full_clean(validate_constraints=False)
        accession.save()
        accession.unstructured_metadata.save()
        accession_generate_blob_task.delay_on_commit(accession.pk)

    return accession


def accession_purge(*, accession: Accession) -> None:
    """Purge an unpublished accession and all associated data."""
    if accession.published:
        raise ValidationError("Cannot remove an accession with an image.")

    for field in Accession._meta.fields:
        if isinstance(field, FileField):
            # save=False because setting the field to None may violate constraints e.g.
            # succeeded accessions must have a thumbnail.
            getattr(accession, field.name).delete(save=False)

    accession.delete()


def bulk_accession_relicense(
    *, accessions: QuerySet[Accession], to_license: str, allow_more_restrictive: bool = False
) -> int:
    if to_license not in CopyrightLicense:
        raise ValueError(f"Invalid license: {to_license}")

    more_permissive_licenses = CopyrightLicense.values[: CopyrightLicense.values.index(to_license)]

    if (
        not allow_more_restrictive
        and accessions.filter(copyright_license__in=more_permissive_licenses).exists()
    ):
        raise ValidationError("Cannot change to a more restrictive license.")

    return accessions.update(copyright_license=to_license)


def bulk_accession_update_metadata(  # noqa: PLR0913
    *,
    user: User,
    metadata: Iterable[tuple[int, Mapping[str, Any]]],
    metadata_application_message: str = "",
    metadata_file_id: int | None = None,
    ignore_image_check: bool = False,
    reset_review: bool = True,
) -> None:
    with (
        transaction.atomic(),
        transaction.get_connection().cursor() as cursor,
        # Lock the longitudinal tables during metadata assignment
        lock_table_for_writes(Lesion),
        lock_table_for_writes(Patient),
        lock_table_for_writes(RcmCase),
    ):
        # it's possible when updating metadata that the constraints are temporarily
        # violated. an example being when updating patient ids, it's possible it
        # could temporarily violate the "identical lesions implies idential patients"
        # constraint and then later be corrected.
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")

        BulkMetadataApplication.objects.create(
            creator=user,
            message=metadata_application_message,
            metadata_file_id=metadata_file_id,
        )

        for batch in batched(metadata, 5_000):
            accessions_by_id = (
                Accession.objects.filter(pk__in=[row[0] for row in batch])
                .select_related(
                    "image",
                    "review",
                    "lesion",
                    "patient",
                    "rcm_case",
                    "cohort",
                    "unstructured_metadata",
                )
                .in_bulk()
            )

            for accession_id, metadata_row in batch:
                accession = accessions_by_id[accession_id]
                accession.update_metadata(
                    user,
                    metadata_row,
                    ignore_image_check=ignore_image_check,
                    reset_review=reset_review,
                )
