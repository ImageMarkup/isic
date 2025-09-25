import djclick as click

from isic.core.models.doi import Doi
from isic.core.services.collection.doi import _datacite_session, collection_build_doi
from isic.core.tasks import fetch_doi_citations_task, fetch_doi_schema_org_dataset_task


@click.command(help="Update all DOIs")
@click.option("--all", "all_", is_flag=True, help="Update all DOIs")
@click.argument("doi_ids", nargs=-1)
def update_dois(all_, doi_ids):
    """
    Update specified DOIs on DataCite or all if --all is specified.

    This is useful after making changes to the metadata provided on DOI creation
    (see collection_build_doi). After updating the DOIs, the citations and schema.org
    information are re-fetched from DataCite.
    """
    doi_queryset = Doi.objects.all() if all_ else Doi.objects.filter(id__in=doi_ids)

    with _datacite_session() as session:
        for doi in doi_queryset.iterator():
            new_doi = collection_build_doi(collection=doi.collection, doi_id=doi.id)
            r = session.put(
                f"/dois/{doi.id}",
                json=new_doi,
                timeout=5,
            )
            if r.status_code != 200:
                click.echo(f"{doi.id} failed: {r.status_code} {r.text}")
            else:
                click.echo(f"{doi.id} succeeded")
                fetch_doi_citations_task.delay_on_commit(doi.id, "Doi")
                fetch_doi_schema_org_dataset_task.delay_on_commit(doi.id, "Doi")
