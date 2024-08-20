from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.db import transaction
from django.db.models import FileField
from django.db.models.query import QuerySet
from s3_file_field.widgets import S3PlaceholderFile

from isic.core.models.base import CopyrightLicense
from isic.ingest.models.accession import Accession
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.unstructured_metadata import UnstructuredMetadata
from isic.ingest.tasks import accession_generate_blob_task


# Note: this method isn't used when creating accessions as part of a zip extraction.
def accession_create(
    *,
    creator: User,
    cohort: Cohort,
    original_blob: File,
    original_blob_name: str,
    original_blob_size: int,
) -> Accession:
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
