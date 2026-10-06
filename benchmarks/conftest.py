from collections.abc import Callable
import tracemalloc

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.test import Client
from django.test.utils import setup_databases, teardown_databases
import pytest

from benchmarks import dataset
from benchmarks.dataset import Viewer
from isic.core.dsl import parse_query
from isic.core.search import IMAGE_INDEX_MAPPINGS, LESION_INDEX_MAPPINGS, get_elasticsearch_client
from isic.core.tasks import sync_elasticsearch_indices_task


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    # pytest-django only creates the test database for tests marked django_db, and the marker
    # wraps each test in a transaction, which some views can't run in (e.g. setting the isolation
    # level). so the database is created the same way, but for every benchmark, and copied from
    # the generated dataset when there is one.
    # migrations create the indices, and refuse to when they exist with other mappings, e.g. from
    # a run of another commit.
    client = get_elasticsearch_client()
    for index in [
        settings.ISIC_ELASTICSEARCH_IMAGES_INDEX,
        settings.ISIC_ELASTICSEARCH_LESIONS_INDEX,
    ]:
        client.indices.delete(index=index, ignore_unavailable=True)
    with django_db_blocker.unblock():
        generated = dataset.template_exists()
        if generated:
            connection.settings_dict["TEST"]["TEMPLATE"] = dataset.template_name()
        config = setup_databases(
            verbosity=0, interactive=False, aliases={"default"}, serialized_aliases=set()
        )
        if not generated:
            dataset.generate()
    yield
    with django_db_blocker.unblock():
        teardown_databases(config, verbosity=0)


@pytest.fixture(scope="session")
def manifest(django_db_setup, django_db_blocker) -> dict:
    with django_db_blocker.unblock():
        return dataset.manifest()


@pytest.fixture(autouse=True)
def _database(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        yield


INDEX_SETTINGS = {
    "index.number_of_replicas": 0,
    # nothing writes during a run. an explicit interval also stops idle shards from making the
    # next search wait for a refresh.
    "index.refresh_interval": "-1",
    # every request should do its full work
    "index.requests.cache.enable": False,
    "index.queries.cache.enabled": False,
}


@pytest.fixture(scope="session")
def search_index(django_db_setup, django_db_blocker):
    """Index the dataset into the benchmark indices."""
    client = get_elasticsearch_client()
    indices = {
        settings.ISIC_ELASTICSEARCH_IMAGES_INDEX: IMAGE_INDEX_MAPPINGS,
        settings.ISIC_ELASTICSEARCH_LESIONS_INDEX: LESION_INDEX_MAPPINGS,
    }
    for index, mappings in indices.items():
        client.indices.delete(index=index, ignore_unavailable=True)
        client.indices.create(index=index, mappings=mappings, settings=INDEX_SETTINGS)
    with django_db_blocker.unblock():
        sync_elasticsearch_indices_task()
    client.indices.refresh(index=list(indices))
    # bulk indexing leaves segments that elasticsearch keeps merging in the background, which
    # slows whichever benchmarks run first. merged up front, every run searches the same index.
    client.indices.forcemerge(index=list(indices), max_num_segments=1)
    client.indices.refresh(index=list(indices))


def _fetch(client: Client, path: str) -> bytes:
    parse_query.cache_clear()
    response = client.get(path)
    if response.status_code != 200:
        raise AssertionError(f"{path}: {response.status_code}")
    if response.streaming:
        return b"".join(response.streaming_content)
    return response.content


@pytest.fixture
def endpoint(manifest) -> Callable[..., Callable[[], bytes]]:
    """
    Log in as a user and return a callable that requests a path.

    The path can be a function of the logged in client. It's requested once before returning.
    """

    def make(user: Viewer, path: str | Callable[[Client], str]) -> Callable[[], bytes]:
        client = Client()
        if user != "anonymous":
            client.force_login(User.objects.get(pk=manifest["users"][user]))
        if callable(path):
            path = path(client)
        _fetch(client, path)
        return lambda: _fetch(client, path)

    return make


@pytest.fixture
def rolled_back() -> Callable[[Callable[[], object]], Callable[[], None]]:
    """
    Wrap a function so each call's writes are rolled back.

    A benchmark calls the function many times, and each call has to start from the same data.
    pytest-django's rollback only happens once, at the end of a test.
    """

    def wrap(fn):
        def run():
            with transaction.atomic():
                fn()
                transaction.set_rollback(True)

        return run

    return wrap


@pytest.fixture
def benchmark_with_memory(benchmark) -> Callable[[Callable[[], object]], None]:
    """
    Benchmark a function, and record the peak memory Python allocates while calling it.

    Memory is measured in a separate call, since tracing allocations slows the function down.
    """

    def run(fn):
        tracemalloc.start()
        try:
            fn()
            benchmark.extra_info["peak_memory_mib"] = tracemalloc.get_traced_memory()[1] / 2**20
        finally:
            tracemalloc.stop()
        benchmark(fn)

    return run
