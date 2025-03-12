from django.conf import settings
import djclick as click
import requests

from isic.core.models.doi import Doi
from isic.core.services.collection.doi import collection_build_doi
from isic.core.tasks import fetch_doi_citations_task, fetch_doi_schema_org_dataset_task


@click.command(help="Update all DOIs")
def update_dois():
    """
    Update all DOIs on DataCite.

    This is useful after making changes to the metadata provided on DOI creation
    (see collection_build_doi). After updating the DOIs, the citations and schema.org
    information are re-fetched from DataCite.
    """
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
            fetch_doi_citations_task.delay_on_commit(doi.id)
            fetch_doi_schema_org_dataset_task.delay_on_commit(doi.id)
