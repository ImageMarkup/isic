from django.conf import settings
import djclick as click

from isic.core.search import get_elasticsearch_client
from isic.core.tasks import sync_elasticsearch_index_task


@click.command(help="Populate the Elasticsearch index")
@click.option("--chunk-size", default=500)
def populate_elasticsearch(chunk_size):
    es = get_elasticsearch_client()
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_INDEX, ignore=[404])
    sync_elasticsearch_index_task(chunk_size)
