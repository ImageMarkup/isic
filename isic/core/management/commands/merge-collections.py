import sys

from django.core.exceptions import ValidationError
import djclick as click

from isic.core.models.collection import Collection
from isic.core.services.collection import collection_merge


@click.command()
@click.argument("collection_id", nargs=-1, type=click.INT)
def merge_collections(collection_id):
    assert len(collection_id) > 1
    collections = []
    for id_ in collection_id:
        collections.append(Collection.objects.get(pk=id_))

    try:
        collection_merge(dest_collection=collections[0], other_collections=collections[1:])
    except ValidationError as e:
        click.secho(e.message, color="red", err=True)
        sys.exit(1)
    else:
        click.secho(
            f"Merged {len(collections[1:])} collections into {collections[0].name}.", color="green"
        )
