import sys

from django.db import transaction
import djclick as click
from isic_metadata.metadata import MetadataRow

from isic.ingest.models import Accession
from isic.ingest.models.metadata_file import MetadataFile


@click.command()
@click.argument('metadata_file_id', nargs=-1, type=click.INT)
def apply_metadata_files(metadata_file_id):
    assert metadata_file_id
    metadata_files = MetadataFile.objects.filter(pk__in=metadata_file_id)
    missing_files = set(metadata_file_id) - set(metadata_files.values_list('pk', flat=True))

    if missing_files:
        click.secho(
            f'Unable to find metadata files: {", ".join(map(str,missing_files))}',
            fg='red',
            err=True,
        )
        sys.exit(1)

    with transaction.atomic():
        try:
            for metadata_file in metadata_files:
                for _, row in metadata_file.to_df().iterrows():
                    accession = Accession.objects.get(
                        blob_name=row['filename'], cohort=metadata_file.cohort
                    )
                    # filename doesn't need to be stored in the metadata
                    del row['filename']
                    metadata = MetadataRow.parse_obj(row)
                    accession.unstructured_metadata.update(metadata.unstructured)
                    accession.metadata.update(
                        metadata.dict(
                            exclude_unset=True, exclude_none=True, exclude={'unstructured'}
                        )
                    )
                    accession.save(update_fields=['metadata', 'unstructured_metadata'])
                click.secho(f'Applied metadata file: {metadata_file.pk}', fg='green')
        except Exception as e:
            click.echo(e)
            click.echo()
            click.secho(
                'Failed to apply metadata files, all changes have been rolled back.', fg='yellow'
            )
            sys.exit(1)
