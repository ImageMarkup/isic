from django.urls import reverse
import pytest

from isic.core.models.collection import Collection


@pytest.mark.django_db
def test_api_request_body_malformed(authenticated_client):
    r = authenticated_client.post(
        reverse("api:collection_create_from_isic_ids"),
        '{"name": "Test Explorer Collection", "isic_ids": [',
        content_type="application/json",
    )

    assert r.status_code == 400, r.content
    assert r.json() == {"detail": "Cannot parse request body"}
    assert not Collection.objects.exists()


@pytest.mark.django_db
def test_api_request_body_too_large(authenticated_client, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 100

    r = authenticated_client.post(
        reverse("api:collection_create_from_isic_ids"),
        {"name": "Test Explorer Collection", "isic_ids": ["ISIC_0000000"] * 10},
        content_type="application/json",
    )

    assert r.status_code == 413, r.content
    assert r.json() == {"detail": "Request body is too large"}
    assert not Collection.objects.exists()
