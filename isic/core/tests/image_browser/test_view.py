from base64 import b64encode
from urllib.parse import urlencode

from django.urls.base import reverse
import pytest

from isic.core.models.image import Image
from isic.core.search import add_to_search_index, get_elasticsearch_client


def _legacy_cursor(position: str) -> str:
    """Build a cursor whose position has a single value, as minted before pin_sort.

    The image browser now orders by ("-pinned", "created"), so a single-value position
    no longer matches the ordering. Such cursors still arrive from bookmarks and crawled
    links predating that change.
    """
    return b64encode(urlencode({"p": position}).encode()).decode()


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_view_using_es_counts(public_image, client, settings):
    settings.ISIC_USE_ELASTICSEARCH_COUNTS = True
    add_to_search_index(public_image)
    get_elasticsearch_client().indices.refresh(index="_all")
    r = client.get(reverse("core/image-browser"))
    assert r.context["total_images"] == 1, r.context
    assert public_image in r.context["images"]


@pytest.mark.django_db
def test_view(public_image, client):
    r = client.get(reverse("core/image-browser"))
    assert r.context["total_images"] == 1
    assert public_image in r.context["images"]


@pytest.mark.django_db
@pytest.mark.usefixtures("_image_browser_scenario")
def test_view_search(client):
    public_image_isic_id = Image.objects.public().first().isic_id
    r = client.get(reverse("core/image-browser"), {"query": f"isic_id:{public_image_isic_id}"})
    assert r.context["total_images"] == 1
    assert r.context["images"][0].isic_id == public_image_isic_id


@pytest.mark.django_db
def test_view_legacy_cursor_falls_back_to_first_page(public_image, client):
    # A cursor built for the pre-pin_sort single-field ("created") ordering carries one
    # position value, which no longer matches the browser's two-field ("-pinned",
    # "created") ordering. Rather than 500, it should be discarded and the first page
    # returned.
    legacy_cursor = _legacy_cursor("2014-10-09 19:36:14.906000+00:00")
    r = client.get(reverse("core/image-browser"), {"cursor": legacy_cursor})
    assert r.status_code == 200
    assert public_image in r.context["images"]
