from django.urls.base import reverse
import pytest

from isic.core.models.image import Image


@pytest.mark.django_db()
def test_view(public_image, client):
    r = client.get(reverse("core/image-browser"))
    assert r.context["total_images"] == 1
    assert public_image in r.context["images"]


@pytest.mark.django_db()
@pytest.mark.usefixtures("_image_browser_scenario")
def test_view_search(client):
    public_image_isic_id = Image.objects.public().first().isic_id
    r = client.get(reverse("core/image-browser"), {"query": f"isic_id:{public_image_isic_id}"})
    assert r.context["total_images"] == 1
    assert r.context["images"][0].isic_id == public_image_isic_id
