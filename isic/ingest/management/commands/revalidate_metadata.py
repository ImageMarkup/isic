import djclick as click
from isic_metadata.metadata import MetadataRow
from pydantic import ValidationError as PydanticValidationError

from isic.ingest.models import Accession


@click.command(help="Revalidate all accession metadata")
def revalidate_metadata():
    accessions = Accession.objects.all()
    num_accessions = accessions.count()
    num_errors = 0

    with click.progressbar(accessions.iterator(), length=num_accessions) as bar:
        for accession in bar:
            try:
                MetadataRow.model_validate(accession.metadata)
            except PydanticValidationError as e:
                num_errors += 1
                click.echo(accession.pk)
                click.echo(e.errors())

    click.echo(f"{num_errors}/{num_accessions} accessions had problems.")
