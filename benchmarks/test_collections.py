from django.urls import reverse
import pytest

from benchmarks.dataset import USERS

# (collection, user)
DETAIL_PAGES = {
    "small": ("small", "anonymous"),
    "medium": ("medium", "anonymous"),
    "all_public": ("all_public", "anonymous"),
    "large": ("large", "staff"),
}


@pytest.mark.parametrize("user", USERS)
def test_collection_list(benchmark, endpoint, user):
    benchmark(endpoint(user, f"{reverse('api:collection_list')}?limit=100"))


@pytest.mark.parametrize("page", DETAIL_PAGES)
def test_collection_detail_page(benchmark, endpoint, manifest, page):
    collection, user = DETAIL_PAGES[page]
    pk = manifest["collections"][collection]
    benchmark(endpoint(user, reverse("core/collection-detail", args=[pk])))


# 1k, 10k and 75k images
@pytest.mark.parametrize("collection", ["small", "medium", "large"])
def test_collection_metadata_export(benchmark_with_memory, endpoint, manifest, collection):
    pk = manifest["collections"][collection]
    benchmark_with_memory(
        endpoint("staff", reverse("core/collection-download-metadata", args=[pk]))
    )
