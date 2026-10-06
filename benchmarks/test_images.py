from urllib.parse import urlencode, urlsplit

from django.test import Client
from django.urls import reverse
import pytest

from benchmarks.dataset import SHOWCASE_ISIC_ID, USERS

# listing and searching take their result counts from elasticsearch
pytestmark = pytest.mark.usefixtures("search_index")

# the shapes of the slowest production searches. collections are named by their manifest key.
SEARCHES = {
    "collection": {"collections": "all_public"},
    "large_collection": {"collections": "large"},
    "diagnosis": {"query": "diagnosis_1:Malignant"},
    "image_type": {"query": "image_type:dermoscopic"},
    "license_in_collection": {"query": "copyright_license:CC-BY", "collections": "all_public"},
    "rcm_case": {"query": "rcm_case_id:*"},
    "nested": {
        "query": 'diagnosis_3:"Melanoma, NOS" OR (image_type:dermoscopic AND age_approx:[30 TO 50])'
    },
    "pin_sort": {"query": "anatom_site_1:Trunk", "pin_sort": "true"},
}


def _second_page(client: Client) -> str:
    first_page = client.get(f"{reverse('api:image_search')}?limit=100").json()
    next_url = urlsplit(first_page["next"])
    return f"{next_url.path}?{next_url.query}"


@pytest.mark.parametrize("user", USERS)
def test_image_list(benchmark, endpoint, user):
    benchmark(endpoint(user, f"{reverse('api:image_list')}?limit=100"))


@pytest.mark.parametrize("user", USERS)
@pytest.mark.parametrize("search", SEARCHES)
def test_image_search(benchmark, endpoint, manifest, search, user):
    query = {"limit": 100, **SEARCHES[search]}
    if "collections" in query:
        query["collections"] = manifest["collections"][query["collections"]]
    benchmark(endpoint(user, f"{reverse('api:image_search')}?{urlencode(query)}"))


@pytest.mark.parametrize("user", USERS)
def test_image_search_second_page(benchmark, endpoint, user):
    benchmark(endpoint(user, _second_page))


@pytest.mark.parametrize("user", ["anonymous", "shares"])
def test_image_detail_api(benchmark, endpoint, user):
    benchmark(endpoint(user, reverse("api:image_detail", args=[SHOWCASE_ISIC_ID])))


@pytest.mark.parametrize("user", USERS)
def test_image_detail_page(benchmark, endpoint, user):
    benchmark(endpoint(user, reverse("core/image-detail", args=[SHOWCASE_ISIC_ID])))


@pytest.mark.parametrize("user", ["shares", "staff"])
def test_similar_images(benchmark, endpoint, user):
    benchmark(endpoint(user, reverse("api:image_similar", args=[SHOWCASE_ISIC_ID])))
