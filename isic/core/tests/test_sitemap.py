from django.urls import reverse
import pytest

from isic.core.tests.factories import DoiFactory


@pytest.mark.django_db
def test_sitemap_dois(client):
    doi = DoiFactory.create()

    response = client.get(reverse("django.contrib.sitemaps.views.sitemap"))
    assert response.status_code == 200
    assert doi.slug in response.content.decode("utf-8")
