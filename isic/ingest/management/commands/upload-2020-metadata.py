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
def upload_2020_metadata():
    u = User.objects.get(email='kurtansn@mskcc.org')
    with open('isic meta_brisbane cohorts 2020_220224.csv') as f:
        df = pd.read_csv(f, header=0)

    # pydantic expects None for the absence of a value, not NaN
    df = df.replace({np.nan: None})

    cohort_files = defaultdict(list)

    for _, (_, row) in enumerate(df.iterrows(), start=2):
        accession: Accession = Accession.objects.select_related('cohort').get(
            image__isic_id=row['isic_id']
        )
        del row['isic_id']
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
        print(m)
