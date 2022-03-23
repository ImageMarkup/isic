import codecs
from collections import defaultdict
import csv
import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
import djclick as click
import numpy as np
import pandas as pd

from isic.ingest.models import Accession
from isic.ingest.models.metadata_file import MetadataFile

StreamWriter = codecs.getwriter('utf-8')


@click.command()
@click.argument('user_id', help='The user to attribute the metadata file to.')
@click.argument('csv_path', help='The path to the CSV of metadata, containing an ISIC ID column.')
@click.argument('isic_id_column', help='The name of the column that refers to the ISIC ID.')
def metadata_files_from_csv(user_id, csv_path, isic_id_column):
    u = User.objects.get(pk=user_id)
    with open(csv_path) as f:
        df = pd.read_csv(f, header=0)

    # pydantic expects None for the absence of a value, not NaN
    df = df.replace({np.nan: None})

    cohort_files = defaultdict(list)

    for _, (_, row) in enumerate(df.iterrows(), start=2):
        accession: Accession = Accession.objects.select_related('cohort').get(
            image__isic_id=row[isic_id_column]
        )
        del row[isic_id_column]
        row['filename'] = accession.blob_name
        cohort_files[accession.cohort.pk].append(dict(row))

    for cohort_id, rows in cohort_files.items():
        blob = StreamWriter(io.BytesIO())
        w = csv.DictWriter(blob, list(set(list(df.columns)) - set('isic_id')) + ['filename'])
        w.writeheader()
        for row in rows:
            w.writerow(row)
        size = blob.tell()
        blob.seek(0)
        blob_name = f'cohort_{cohort_id}_metadata.csv'
        blob = SimpleUploadedFile(blob_name, blob.getvalue(), 'text/csv')

        m = MetadataFile.objects.create(
            creator=u, cohort_id=cohort_id, blob=blob, blob_size=size, blob_name=blob_name
        )
        click.secho(f'Created metadata file: {m.pk}, authored by {u.email}', fg='green')
