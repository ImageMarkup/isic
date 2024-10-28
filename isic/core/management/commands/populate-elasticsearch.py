from django.conf import settings
import djclick as click

from isic.core.search import (
    get_elasticsearch_client,
)
from isic.core.tasks import sync_elasticsearch_indices_task


@click.command(help="Populate the Elasticsearch indices")
@click.option("--chunk-size", default=500)
def populate_elasticsearch(chunk_size):
    es = get_elasticsearch_client()

    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, ignore=[404])
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, ignore=[404])

    sync_elasticsearch_indices_task()

    es.indices.refresh(index="_all")

    click.echo("Done", color="green")
