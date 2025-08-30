import pytest

from isic.core.models.collection_count import CollectionCount
from isic.core.tasks import refresh_materialized_view_collection_counts_task


@pytest.mark.django_db
def test_materialized_view_includes_empty_collections(collection_factory, image_factory):
    empty_collection = collection_factory()
    collection_with_image = collection_factory()

    image = image_factory()
    collection_with_image.images.add(image)

    refresh_materialized_view_collection_counts_task()

    cached_with_image = CollectionCount.objects.get(id=collection_with_image.id)
    assert cached_with_image.image_count == 1

    cached_empty = CollectionCount.objects.get(id=empty_collection.id)
    assert cached_empty.image_count == 0
