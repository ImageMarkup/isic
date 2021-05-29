from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_core_api_stats(client):
    r = client.get(reverse('core/api/stats'))
    assert r.status_code == 200
