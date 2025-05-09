import csv
from itertools import batched
from pathlib import Path

from django.contrib.auth.models import User
import djclick as click

from isic.ingest.models import Accession
from isic.ingest.services.accession import bulk_accession_update_metadata


@click.command()
@click.argument("user_id")
@click.argument("csv_path")
@click.argument("message")
def apply_published_metadata(user_id, csv_path, message):
    user = User.objects.get(pk=user_id)

    def rows_by_accession_id():
        with Path(csv_path).open() as f:
            reader = csv.DictReader(f)

            for batch in batched(reader, 5_000):
                click.echo(f"Processing batch of {len(batch)}")
                accession_id_by_isic_id = dict(
                    Accession.objects.filter(image__isic_id__in=[row["isic_id"] for row in batch])
                    .values_list("image__isic_id", "id")
                    .order_by()
                )

                for row in batch:
                    accession_id = accession_id_by_isic_id[row["isic_id"]]

                    # filename doesn't need to be stored in the metadata
                    for col in ["filename", "isic_id"]:
                        if col in row:
                            del row[col]

                    yield accession_id, row

    bulk_accession_update_metadata(
        user=user,
        metadata=rows_by_accession_id(),
        metadata_application_message=message,
        ignore_image_check=True,
        reset_review=False,
    )

    click.secho(f"Applied CSV {csv_path} as {user.email}", fg="green")
