from django.db import transaction
import djclick as click
from isic_metadata.metadata import MetadataRow

from isic.ingest.models import Accession
from isic.ingest.models.metadata_file import MetadataFile


@click.command()
def apply_2020_metadata():
    for mf in MetadataFile.objects.filter(
        blob_name__in=['cohort_188_metadata.csv', 'cohort_181_metadata.csv']
    ):
        with transaction.atomic():
            for _, row in mf.to_df().iterrows():
                accession = Accession.objects.get(blob_name=row['filename'], cohort=mf.cohort)
                # filename doesn't need to be stored in the metadata since it's equal to blob_name
                del row['filename']
                metadata = MetadataRow.parse_obj(row)
                accession.unstructured_metadata.update(metadata.unstructured)
                accession.metadata.update(
                    metadata.dict(exclude_unset=True, exclude_none=True, exclude={'unstructured'})
                )
                accession.save(update_fields=['metadata', 'unstructured_metadata'])
