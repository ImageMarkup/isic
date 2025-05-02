from django.urls.base import reverse
import pytest

from isic.stats.models import SearchQuery


@pytest.mark.django_db
def test_api_stats(client):
    r = client.get(reverse("api:stats"))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("query", "expected_count"),
    [
        ("", 0),
        ("diagnosis_1:Benign AND -melanocytic:*", 1),
    ],
)
def test_search_query_logging(client, query, expected_count):
    response = client.get(reverse("api:search_images"), {"query": query})
    assert response.status_code == 200
    assert SearchQuery.objects.count() == expected_count
    if expected_count > 0:
        assert SearchQuery.objects.last().value == query
