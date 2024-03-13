from urllib.parse import urlparse

import pytest


@pytest.mark.django_db()
def test_pagination(image_factory, staff_client):
    images = [image_factory() for _ in range(2)]

    resp = staff_client.get("/api/v2/images/", data={"limit": 1})

    assert resp.status_code == 200, resp.json()
    assert resp.json()["count"] == 2
    assert len(resp.json()["results"]) == 1
    # default order is -created, so second image should be first
    assert resp.json()["results"][0]["isic_id"] == images[1].isic_id
    assert resp.json()["previous"] is None
    parsed = urlparse(resp.json()["next"])
    assert parsed.path == "/api/v2/images/"
    assert "cursor" in parsed.query

    # follow next page link
    resp = staff_client.get(resp.json()["next"])
    assert resp.status_code == 200, resp.json()
    # counts are not included in paginated responses
    assert resp.json()["count"] is None
    assert len(resp.json()["results"]) == 1
    assert resp.json()["results"][0]["isic_id"] == images[0].isic_id
    assert resp.json()["next"] is None
    parsed = urlparse(resp.json()["previous"])
    assert parsed.path == "/api/v2/images/"
    assert "cursor" in parsed.query

    # make sure previous links also work
    resp = staff_client.get(resp.json()["previous"], data={"limit": 1})
    assert resp.status_code == 200, resp.json()
    assert resp.json()["count"] == 2
    assert len(resp.json()["results"]) == 1
    assert resp.json()["results"][0]["isic_id"] == images[1].isic_id
    assert resp.json()["previous"] is None
