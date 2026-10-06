from django.urls import reverse
import pytest

from benchmarks.dataset import SHOWCASE_LESION_ID, USERS

# the lesion list takes its count from elasticsearch
pytestmark = pytest.mark.usefixtures("search_index")


@pytest.mark.parametrize("user", USERS)
def test_lesion_list(benchmark, endpoint, user):
    benchmark(endpoint(user, f"{reverse('api:lesion_list')}?limit=100"))


def test_lesion_detail_api(benchmark, endpoint):
    benchmark(endpoint("anonymous", reverse("api:lesion_detail", args=[SHOWCASE_LESION_ID])))


def test_lesion_detail_page(benchmark, endpoint):
    benchmark(endpoint("anonymous", reverse("core/lesion-detail", args=[SHOWCASE_LESION_ID])))
