from base64 import b64encode

from django.urls.base import reverse
import pytest

from isic.core.models.image import Image
from isic.core.search import add_to_search_index, get_elasticsearch_client


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
@pytest.mark.parametrize(
    "cursor",
    [
        # not decodable as a cursor
        "not-a-cursor",
        # structurally valid, but the position carries a single value while the browser orders
        # by ("-pinned", "created"), so it fails the position/ordering arity check
        b64encode(b"r=1&p=2020-03-29+19%3A35%3A52.").decode(),
        # structurally valid, right number of position values, but the "created" value is a
        # truncated datetime that can't be parsed for its field
        b64encode(b"r=1&p=1|2020-03-29+19%3A35%3A52.").decode(),
    ],
    ids=["undecodable", "wrong_arity", "invalid_position"],
)
def test_view_invalid_cursor(client, cursor):
    r = client.get(reverse("core/image-browser"), {"cursor": cursor})
    assert r.status_code == 400


@pytest.mark.django_db
@pytest.mark.usefixtures("_image_browser_scenario")
def test_view_search(client):
    public_image_isic_id = Image.objects.public().first().isic_id
    r = client.get(reverse("core/image-browser"), {"query": f"isic_id:{public_image_isic_id}"})
    assert r.context["total_images"] == 1
    assert r.context["images"][0].isic_id == public_image_isic_id
