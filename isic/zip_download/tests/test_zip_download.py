from urllib.parse import parse_qs, urlparse

from django.urls.base import reverse
import pytest


@pytest.fixture
def random_images_with_licenses(image_factory):
    image = image_factory(
        accession__metadata={"diagnosis": "melanoma"},
        public=True,
    )
    image.accession.copyright_license = "CC-0"
    image.accession.save()

    image = image_factory(
        accession__metadata={"diagnosis": "nevus"},
        public=True,
    )
    # TODO: factory boy overriding doesn't work for subfields of accession__cohort
    image.accession.copyright_license = "CC-BY"
    image.accession.save()


@pytest.mark.django_db
def test_zip_download_licenses(authenticated_client, random_images_with_licenses):
    r = authenticated_client.post(
        reverse("zip-download/api/url"), {"query": ""}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(reverse("zip-download/api/file-listing"), data={"token": token[0]})
    assert r.status_code == 200, r.json()

    assert any("CC-0" in result["url"] for result in r.json()["results"])
    assert any("CC-BY" in result["url"] for result in r.json()["results"])
    assert not any("CC-BY-NC" in result["url"] for result in r.json()["results"])


@pytest.mark.django_db
def test_zip_download_listing(authenticated_client, random_images_with_licenses, mocker):
    r = authenticated_client.post(
        reverse("zip-download/api/url"), {"query": ""}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    # mock the page size to 1 to make sure pagination is working
    with mocker.patch(
        "rest_framework.pagination.CursorPagination.get_page_size",
        return_value=1,
    ):
        r = authenticated_client.get(
            reverse("zip-download/api/file-listing"), data={"token": token[0]}
        )
        assert r.status_code == 200, r.json()
        # the first page is size 5 (1 limit + 1 metadata + 1 attribution + 2 licenses)
        assert len(r.json()["results"]) == 5, r.json()
        assert r.json()["next"], r.json()

        r = authenticated_client.get(r.json()["next"])
        assert r.status_code == 200, r.json()
        assert len(r.json()["results"]) == 1, r.json()
        assert not r.json()["next"], r.json()
