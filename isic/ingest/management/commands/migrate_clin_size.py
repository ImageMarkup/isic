from django.contrib.auth.models import User
from django.db import transaction
import djclick as click

from isic.ingest.models.accession import Accession


@click.command()
@click.argument('user_id')
def migrate_clin_size(user_id: int):
    user = User.objects.get(id=user_id)

    with transaction.atomic():
        accessions = Accession.objects.exclude(metadata__clin_size_long_diam_mm=None)
        with click.progressbar(accessions.iterator(), length=accessions.count()) as bar:
            for accession in bar:
                accession.update_metadata(
                    user,
                    {
                        'clin_size_long_diam_mm': round(
                            accession.metadata['clin_size_long_diam_mm'], ndigits=1
                        )
                    },
                    ignore_image_check=True,
                    reset_review=False,
                )
