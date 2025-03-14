import sys
import traceback

from django.contrib.auth.models import User
from django.db import transaction
import djclick as click

from isic.ingest.models import Accession
from isic.ingest.models.metadata_file import MetadataFile


@click.command()
@click.argument("user_id")
@click.argument("metadata_file_id", nargs=-1, type=click.INT)
def apply_metadata_files(user_id, metadata_file_id):
    user = User.objects.get(pk=user_id)
    metadata_files = MetadataFile.objects.filter(pk__in=metadata_file_id)
    missing_files = set(metadata_file_id) - set(metadata_files.values_list("pk", flat=True))

    if missing_files:
        click.secho(
            f"Unable to find metadata files: {', '.join(map(str, missing_files))}",
            fg="red",
            err=True,
        )
        sys.exit(1)

    with transaction.atomic():
        try:
            for metadata_file in metadata_files:
                with metadata_file.blob.open("rb") as fh:
                    for row in metadata_file.to_dict_reader(fh):
                        accession = Accession.objects.get(
                            original_blob_name=row["filename"], cohort=metadata_file.cohort
                        )
                        # filename doesn't need to be stored in the metadata
                        del row["filename"]
                        accession.update_metadata(
                            user, row, ignore_image_check=True, reset_review=False
                        )
                click.secho(f"Applied metadata file {metadata_file.pk} as {user.email}", fg="green")
        except Exception:  # noqa: BLE001
            click.echo(traceback.format_exc(), err=True)
            click.echo()
            click.secho(
                "Failed to apply metadata files, all changes have been rolled back.", fg="yellow"
            )
            sys.exit(1)
