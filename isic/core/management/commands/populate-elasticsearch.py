from django.conf import settings
from django.db.models import Prefetch
import djclick as click

from isic.core.models.image import Image
from isic.core.search import (
    IMAGE_INDEX_MAPPINGS,
    LESION_INDEX_MAPPINGS,
    bulk_add_to_search_index,
    get_elasticsearch_client,
    maybe_create_index,
)
from isic.ingest.models.accession import Accession
from isic.ingest.models.lesion import Lesion


@click.command(help="Populate the Elasticsearch indices")
@click.option("--chunk-size", default=500)
def populate_elasticsearch(chunk_size):
    es = get_elasticsearch_client()

    # create/populate images index
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, ignore=[404])
    maybe_create_index(settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, IMAGE_INDEX_MAPPINGS)
    click.echo("Populating images index")
    bulk_add_to_search_index(
        settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
        Image.objects.with_elasticsearch_properties().all(),
        chunk_size=chunk_size,
    )

    # create/populate lesions index
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, ignore=[404])
    maybe_create_index(settings.ISIC_ELASTICSEARCH_LESIONS_INDEX, LESION_INDEX_MAPPINGS)
    click.echo("Populating lesions index")
    bulk_add_to_search_index(
        settings.ISIC_ELASTICSEARCH_LESIONS_INDEX,
        Lesion.objects
        # only include lesions with images
        .has_images()
        # only look at published accessions
        .prefetch_related(Prefetch("accessions", queryset=Accession.objects.published().order_by()))
        # include elasticsearch properties for the images
        .prefetch_related(
            Prefetch(
                "accessions__image",
                queryset=Image.objects.with_elasticsearch_properties().order_by(),
            )
        )
        .all()
        .order_by(),
        chunk_size=chunk_size,
    )
    es.indices.refresh(index="_all")

    click.echo("Done", color="green")
