from itertools import chain

import djclick as click

from isic.core.models.doi import Doi, DraftDoi
from isic.core.services.collection.doi import _datacite_session, build_collection_doi
from isic.core.tasks import fetch_doi_citations_task, fetch_doi_schema_org_dataset_task


@click.command(help="Update DOIs on DataCite")
@click.argument("doi_ids", nargs=-1)
def update_dois(doi_ids):
    """
    Update DOIs (published and draft) on DataCite.

    If specific DOI IDs are provided, only those are updated. Otherwise all DOIs are updated.

    This is useful after making changes to the metadata provided on DOI creation
    (see build_collection_doi). After updating the DOIs, the citations and schema.org
    information are re-fetched from DataCite.
    """
    if doi_ids:
        dois = chain(
            ((doi, False) for doi in Doi.objects.filter(id__in=doi_ids).iterator()),
            ((doi, True) for doi in DraftDoi.objects.filter(id__in=doi_ids).iterator()),
        )
    else:
        dois = chain(
            ((doi, False) for doi in Doi.objects.iterator()),
            ((doi, True) for doi in DraftDoi.objects.iterator()),
        )

    with _datacite_session() as session:
        for doi, is_draft in dois:
            doi_type = "DraftDoi" if is_draft else "Doi"
            new_doi = build_collection_doi(
                collection=doi.collection,
                doi_id=doi.id,
                is_draft=is_draft,
                related_identifiers=doi.related_identifiers.all(),
            )
            r = session.put(
                f"/dois/{doi.id}",
                json=new_doi,
                timeout=5,
            )
            if r.status_code != 200:
                click.echo(f"{doi.id} ({doi_type}) failed: {r.status_code} {r.text}")
            else:
                click.echo(f"{doi.id} ({doi_type}) succeeded")
                fetch_doi_citations_task.delay_on_commit(doi.id, doi_type)
                fetch_doi_schema_org_dataset_task.delay_on_commit(doi.id, doi_type)
