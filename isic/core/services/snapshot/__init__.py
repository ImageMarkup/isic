import tempfile
import zipfile

from django.db import connection, transaction
from django.db.models import QuerySet
from django.template.loader import render_to_string

from isic.core.models import Image, SupplementalFile
from isic.core.services import image_metadata_csv
from isic.core.utils.csv import EscapingDictWriter
from isic.zip_download.api import get_attributions

CHUNK_SIZE = 5 * 1024 * 1024  # 5MB


def snapshot_images(
    *, qs: QuerySet[Image], supplemental_files: QuerySet[SupplementalFile] | None = None
) -> tuple[str, str]:
    with transaction.atomic():
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

        qs = qs.select_related("accession").all()

        with (
            tempfile.NamedTemporaryFile("wb", delete=False) as snapshot_file,
            zipfile.ZipFile(snapshot_file, "w") as bundle,
        ):
            for image in qs.iterator():
                with image.blob.open("rb") as blob:
                    bundle.writestr(f"images/{image.isic_id}.{image.extension}", blob.read())

            # the metadata csv could be large enough that it needs to be written to disk first
            with tempfile.NamedTemporaryFile("w", delete=False) as metadata_file:
                collection_metadata = image_metadata_csv(qs=qs)
                writer = EscapingDictWriter(metadata_file, fieldnames=next(collection_metadata))
                writer.writeheader()
                for row in collection_metadata:
                    assert isinstance(row, dict)  # noqa: S101
                    writer.writerow(row)
                metadata_file.flush()

                bundle.write(metadata_file.name, "metadata.csv")

            for license_ in (
                qs.values_list("accession__copyright_license", flat=True).order_by().distinct()
            ):
                bundle.writestr(
                    f"licenses/{license_}.txt",
                    render_to_string(f"zip_download/{license_}.txt"),
                )

            attributions = get_attributions(qs.values_list("accession__attribution", flat=True))
            bundle.writestr("attribution.txt", "\n\n".join(attributions))

            supplemental_files = (
                supplemental_files
                if supplemental_files is not None
                else SupplementalFile.objects.none()
            )
            for supplemental_file in supplemental_files.iterator():
                with (
                    supplemental_file.blob.open("rb") as blob,
                    bundle.open(f"supplements/{supplemental_file.filename}", "w") as zip_file,
                ):
                    chunk = blob.read(CHUNK_SIZE)
                    while chunk:
                        zip_file.write(chunk)
                        chunk = blob.read(CHUNK_SIZE)

        return snapshot_file.name, metadata_file.name
