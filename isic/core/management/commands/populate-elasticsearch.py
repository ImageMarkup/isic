from django.conf import settings
import djclick as click

from isic.core.search import (
    IMAGE_INDEX_MAPPINGS,
    LESION_INDEX_MAPPINGS,
    get_elasticsearch_client,
    maybe_create_index,
)
from isic.core.tasks import sync_elasticsearch_indices_task


@click.command(help="Populate the Elasticsearch indices")
@click.option("--chunk-size", default=500)
def populate_elasticsearch(chunk_size):
    es = get_elasticsearch_client()

    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, ignore_unavailable=True)
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, ignore_unavailable=True)

    maybe_create_index(settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, IMAGE_INDEX_MAPPINGS)
    maybe_create_index(settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, LESION_INDEX_MAPPINGS)

    sync_elasticsearch_indices_task()

    es.indices.refresh(index="_all")

    click.echo("Done", color="green")
