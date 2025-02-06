from django.urls import reverse
import pytest

from isic.core.tasks import sync_elasticsearch_indices_task


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_faceting_cache(client, django_assert_max_num_queries):
    with django_assert_max_num_queries(1):
        client.get(reverse("api:get_facets"))

    with django_assert_max_num_queries(0):
        client.get(reverse("api:get_facets"))

    with django_assert_max_num_queries(1):
        client.get(reverse("api:get_facets"), {"query": "age_approx:50"})

    with django_assert_max_num_queries(0):
        client.get(reverse("api:get_facets"), {"query": "age_approx:50"})

    sync_elasticsearch_indices_task()

    with django_assert_max_num_queries(1):
        client.get(reverse("api:get_facets"))

    with django_assert_max_num_queries(1):
        client.get(reverse("api:get_facets"), {"query": "age_approx:50"})
