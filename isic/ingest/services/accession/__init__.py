from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files.base import File
from s3_file_field.widgets import S3PlaceholderFile

from isic.ingest.models.accession import Accession
from isic.ingest.models.cohort import Cohort
from isic.ingest.tasks import accession_generate_blob_task


def accession_create(
    *, creator: User, cohort: Cohort, original_blob: File, blob_name: str
) -> Accession:
    # TODO: should the user this is acting on behalf of be the same as the creator?
    if not creator.has_perm('ingest.add_accession', cohort):
        raise ValidationError('You do not have permission to add an image to this cohort.')

    if cohort.accessions.filter(blob_name=blob_name).exists():
        raise ValidationError('An accession with this name already exists.')

    if isinstance(original_blob, S3PlaceholderFile):
        original_blob = original_blob.name

    accession = Accession.objects.create(
        creator=creator, cohort=cohort, original_blob=original_blob, blob_name=blob_name
    )

    accession_generate_blob_task.delay(accession.pk)

    return accession
