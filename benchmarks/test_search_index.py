"""Endpoints answered by elasticsearch, against the indexed dataset."""

from urllib.parse import urlencode

from django.urls import reverse
import pytest

from benchmarks.dataset import USERS

pytestmark = [
    pytest.mark.usefixtures("search_index"),
    # elasticsearch's JVM is slower until it warms up
    pytest.mark.benchmark(warmup=True, warmup_iterations=100),
]


@pytest.mark.parametrize("user", USERS)
def test_facets(benchmark, endpoint, user):
    benchmark(endpoint(user, reverse("api:image_facets")))


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("query", ["", "diagnosis_1:Malignant"])
def test_search_size(benchmark, endpoint, query, user):
    benchmark(endpoint(user, f"{reverse('api:image_search_size')}?{urlencode({'query': query})}"))
