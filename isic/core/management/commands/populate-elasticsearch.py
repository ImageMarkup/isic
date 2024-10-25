from django.conf import settings
import djclick as click

from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index, get_elasticsearch_client, maybe_create_index


@click.command(help="Populate the Elasticsearch index")
@click.option("--chunk-size", default=500)
def populate_elasticsearch(chunk_size):
    es = get_elasticsearch_client()
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, ignore=[404])
    maybe_create_index()
    bulk_add_to_search_index(
        Image.objects.with_elasticsearch_properties().all(), chunk_size=chunk_size
    )
    es.indices.refresh(index="_all")
