from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_sitemap_dois(client, doi_factory):
    doi = doi_factory()
    response = client.get(reverse("django.contrib.sitemaps.views.sitemap"))
    assert response.status_code == 200
    assert doi.slug in response.content.decode("utf-8")
