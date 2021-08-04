from django.conf import settings
import pytest

from isic.core.search import get_elasticsearch_client, maybe_create_index


@pytest.fixture
def search_index():
    es = get_elasticsearch_client()
    maybe_create_index()
    yield
    es.indices.delete(settings.ISIC_ELASTICSEARCH_INDEX)
