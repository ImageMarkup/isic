from django.core.exceptions import ValidationError
from django.db.models import FileField

from isic.ingest.models.zip_upload import ZipUpload


def zip_upload_purge(*, zip_upload: ZipUpload) -> None:
    """
    Purge a zip_upload object assuming there are no relevant accessions.

    This is really only useful after accession_purge has been called on all relevant accessions.
    """
    if zip_upload.accessions.exists():
        raise ValidationError("Cannot remove a zip_upload with associated accessions.")

    for field in ZipUpload._meta.fields:
        if isinstance(field, FileField):
            getattr(zip_upload, field.name).delete(save=False)

    zip_upload.delete()
