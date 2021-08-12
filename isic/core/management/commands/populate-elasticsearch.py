from django.conf import settings
import djclick as click

from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index, get_elasticsearch_client, maybe_create_index


@click.command(help='Populate the Elasticsearch index')
def populate_elasticsearch():
    es = get_elasticsearch_client()
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_INDEX)
    maybe_create_index()
    bulk_add_to_search_index(Image.objects.all())
    es.indices.refresh(index='_all')
