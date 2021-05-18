import djclick as click

from isic.ingest.models import Accession
from isic.ingest.validators import MetadataRow


@click.command(help='Revalidate all accession metadata')
def revalidate_metadata():
    accessions = Accession.objects.values_list('pk', 'metadata')
    num_accessions = accessions.count()
    num_errors = 0

    with click.progressbar(accessions) as bar:
        for (pk, metadata) in bar:
            try:
                MetadataRow.parse_obj(metadata)
            except Exception as e:
                num_errors += 1
                click.echo(pk)
                click.echo(e.errors())

    click.echo(f'{num_errors}/{num_accessions} accessions had problems.')
