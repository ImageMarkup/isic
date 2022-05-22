import djclick as click

from isic.ingest.models import Accession


@click.command(help='Populate original blob sizes')
def populate_blob_sizes():
    accessions = Accession.objects.filter(original_blob_size=None).iterator()
    with click.progressbar(accessions) as bar:
        for accession in bar:
            accession.original_blob_size = accession.original_blob.size
            accession.save(update_fields=['original_blob_size'])
