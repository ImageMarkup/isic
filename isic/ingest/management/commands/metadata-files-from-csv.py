import codecs
from collections import defaultdict
import csv
import io
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import djclick as click

from isic.core.utils.csv import EscapingDictWriter
from isic.ingest.models import Accession
from isic.ingest.models.metadata_file import MetadataFile

StreamWriter = codecs.getwriter("utf-8")


@click.command()
@click.argument("user_id")
@click.argument("csv_path")
@click.argument("isic_id_column")
def metadata_files_from_csv(user_id, csv_path, isic_id_column):
    """
    Create MetadataFile objects from a CSV that refers to already published images.

    These can be later applied with apply-metadata-files.

    USER_ID is the user the MetadataFile objects will be owned by.

    CSV_PATH is the path to the csv of the metadata, which must contain a column with
    the ISIC ID.

    ISIC_ID_COLUMN is the name of the column that refers to the ISIC ID.
    """
    u = User.objects.get(pk=user_id)
    columns_to_drop = {"isic_id", "filename", isic_id_column}

    cohort_files = defaultdict(list)
    cohort_columns = defaultdict(set)

    with Path(csv_path).open() as f:
        reader = csv.DictReader(f)

        for row in reader:
            accession: Accession = Accession.objects.select_related("cohort").get(
                image__isic_id=row[isic_id_column]
            )
            for column in columns_to_drop:
                if column in row:
                    del row[column]
            row["filename"] = accession.original_blob_name
            cohort_columns[accession.cohort.pk] |= set(row.keys())
            cohort_files[accession.cohort.pk].append(dict(row))

    for cohort_id, rows in cohort_files.items():
        blob = StreamWriter(io.BytesIO())
        w = EscapingDictWriter(blob, list(cohort_columns[cohort_id]))
        w.writeheader()
        for row in rows:
            w.writerow(row)
        size = blob.tell()
        blob.seek(0)
        blob_name = f"cohort_{cohort_id}_metadata.csv"
        blob_file = SimpleUploadedFile(blob_name, blob.getvalue(), "text/csv")

        m = MetadataFile.objects.create(
            creator=u,
            cohort_id=cohort_id,
            blob=blob_file,
            blob_size=size,
            blob_name=blob_name,
        )
        click.secho(f"Created metadata file: {m.pk}, authored by {u.email}", fg="green")
