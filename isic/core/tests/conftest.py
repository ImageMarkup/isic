from django.conf import settings
import pytest

from isic.core.search import get_elasticsearch_client, maybe_create_index


@pytest.fixture
def search_index():
    es = get_elasticsearch_client()
    maybe_create_index()
    yield
    es.indices.delete(settings.ISIC_ELASTICSEARCH_INDEX)


@pytest.fixture
def private_collection(collection_factory):
    collection = collection_factory(public=False)
    return collection


@pytest.fixture
def public_collection(collection_factory):
    collection = collection_factory(public=True)
    return collection


@pytest.fixture
def other_contributor(user_factory, contributor_factory):
    user = user_factory()
    contributor = contributor_factory(owners=[user])
    return contributor


@pytest.fixture
def contributors(contributor, other_contributor):
    return [contributor, other_contributor]


@pytest.fixture
def private_image(image_factory):
    return image_factory(public=False)


@pytest.fixture
def public_image(image_factory):
    return image_factory(public=True)
