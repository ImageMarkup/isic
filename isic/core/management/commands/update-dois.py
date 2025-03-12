from django.conf import settings
import djclick as click
import requests

from isic.core.models.doi import Doi
from isic.core.services.collection.doi import collection_build_doi


@click.command(help="Update all DOIs")
def update_dois():
    for doi in Doi.objects.iterator():
        new_doi = collection_build_doi(collection=doi.collection, doi_id=doi.id)
        r = requests.put(
            f"{settings.ISIC_DATACITE_API_URL}/dois/{doi.id}",
            auth=(settings.ISIC_DATACITE_USERNAME, settings.ISIC_DATACITE_PASSWORD),
            timeout=5,
            json=new_doi,
        )
        if r.status_code != 200:
            click.echo(f"{doi.id} failed: {r.status_code} {r.text}")
        else:
            click.echo(f"{doi.id} succeeded")
