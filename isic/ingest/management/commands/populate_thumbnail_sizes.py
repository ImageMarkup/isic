from django.db import transaction
import djclick as click

from isic.ingest.models.accession import Accession


@click.command()
def populate_thumbnail_sizes():
    with transaction.atomic():
        accessions = Accession.objects.filter(thumbnail_256_size=None).exclude(thumbnail_256='')
        with click.progressbar(accessions.iterator(), length=accessions.count()) as bar:
            for accession in bar:
                accession.thumbnail_256_size = accession.thumbnail_256.size
                accession.save(update_fields=['thumbnail_256_size'])
