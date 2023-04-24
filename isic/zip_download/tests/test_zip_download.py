from urllib.parse import parse_qs, urlparse

from django.urls.base import reverse
import pytest


@pytest.fixture
def random_images(image_factory):
    image_factory(accession__metadata={"diagnosis": "melanoma"}, public=True)
    image_factory(accession__metadata={"diagnosis": "nevus"}, public=True)


@pytest.mark.django_db
def test_zip_download_listing(authenticated_api_client, random_images, mocker):
    r = authenticated_api_client.post(reverse("zip-download/api/url"), {"query": ""})
    assert r.status_code == 200, r.data
    parsed_url = urlparse(r.data)
    token = parse_qs(parsed_url.query)["zsid"]

    # mock the page size to 1 to make sure pagination is working
    with mocker.patch(
        "rest_framework.pagination.CursorPagination.get_page_size",
        return_value=1,
    ):
        r = authenticated_api_client.get(
            reverse("zip-download/api/file-listing"), data={"token": token[0]}
        )
        assert r.status_code == 200, r.json()
        # the first page is size 3 (1 limit + 1 metadata + 1 attribution)
        assert len(r.json()["results"]) == 3, r.json()
        assert r.json()["next"], r.json()

        r = authenticated_api_client.get(r.json()["next"])
        assert r.status_code == 200, r.json()
        assert len(r.json()["results"]) == 1, r.json()
        assert not r.json()["next"], r.json()
