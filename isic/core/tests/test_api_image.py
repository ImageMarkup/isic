import pytest
import requests

from isic.core.search import add_to_search_index, get_elasticsearch_client


@pytest.fixture
def searchable_image(search_index, image_factory):
    image = image_factory(accession__metadata={"age": 52}, public=True)
    add_to_search_index(image)
    # Ensure that the image is available in the index for search
    get_elasticsearch_client().indices.refresh(index="_all")
    return image


@pytest.mark.django_db
def test_core_api_image_ages_are_always_rounded(
    authenticated_client, staff_client, searchable_image
):
    for client_ in [authenticated_client, staff_client]:
        r = client_.get("/api/v2/images/")
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1
        assert r.json()["results"][0]["metadata"]["clinical"]["age_approx"] == 50

        r = client_.get(f"/api/v2/images/{searchable_image.isic_id}/")
        assert r.status_code == 200, r.json()
        assert r.json()["metadata"]["clinical"]["age_approx"] == 50

        # test search isn't leaking ages
        r = client_.get("/api/v2/images/search/", {"query": "age_approx:50"})
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 1
        assert r.json()["results"][0]["metadata"]["clinical"]["age_approx"] == 50

        r = client_.get("/api/v2/images/search/", {"query": "age_approx:52"})
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == 0


@pytest.mark.django_db
@pytest.mark.parametrize("image_file", ["full", "thumbnail_256"])
def test_api_image_urls_thumbnail_256(client, image_factory, image_file):
    image = image_factory(public=True)

    api_resp = client.get(f"/api/v2/images/{image.isic_id}/")

    assert isinstance(api_resp.json().get("files"), dict)
    assert isinstance(api_resp.json()["files"].get(image_file), dict)
    assert isinstance(api_resp.json()["files"][image_file]["url"], str)
    image_url = api_resp.json()["files"][image_file]["url"]
    assert image_url

    # "stream=True", as there's no need to download the actual response body
    storage_resp = requests.get(image_url, stream=True)
    assert storage_resp.status_code == 200
    # TODO: MinioStorage doesn't respect FieldFile.content_type, so there's no point to this
    # assertion, even though it succeeds
    # assert storage_resp.headers['Content-Type'] == 'image/jpeg'
    # TODO: Fix Content-Disposition
    # assert 'thumbnail' in storage_resp.headers['Content-Disposition']
