import csv
from itertools import batched
from pathlib import Path

from django.contrib.auth.models import User
from django.db import transaction
import djclick as click

from isic.ingest.models import Accession
from isic.ingest.services.accession import bulk_accession_update_metadata


@click.command()
@click.argument("user_id")
@click.argument("csv_path")
@click.argument("message")
@click.option("--defer-constraints", is_flag=True, help="Defer all constraints for the transaction")
def apply_published_metadata(user_id, csv_path, message, defer_constraints):
    user = User.objects.get(pk=user_id)

    def rows_by_accession_id():
        with Path(csv_path).open() as f:
            reader = csv.DictReader(f)

            for batch in batched(reader, 5_000):
                click.echo(f"Processing batch of {len(batch)}")
                accession_id_by_isic_id = dict(
                    Accession.objects.filter(
                        image__isic_id__in=[row["isic_id"] for row in batch]
                    ).values_list("image__isic_id", "id")
                )

                for row in batch:
                    accession_id = accession_id_by_isic_id[row["isic_id"]]

                    # filename doesn't need to be stored in the metadata
                    for col in ["filename", "isic_id"]:
                        if col in row:
                            del row[col]

                    yield accession_id, row

    with transaction.atomic():
        if defer_constraints:
            with transaction.get_connection().cursor() as cursor:
                # it's possible when updating metadata that the constraints are temporarily
                # violated. an example being when updating patient ids, it's possible it
                # could temporarily violate the "identical lesions implies idential patients"
                # constraint and then later be corrected.
                cursor.execute("SET CONSTRAINTS ALL DEFERRED")

        bulk_accession_update_metadata(
            user=user,
            metadata=rows_by_accession_id(),
            metadata_application_message=message,
            ignore_image_check=True,
            reset_review=False,
        )

    click.secho(f"Applied CSV {csv_path} as {user.email}", fg="green")
