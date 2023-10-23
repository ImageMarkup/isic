from base64 import b64encode
from urllib.parse import parse_qs, urlparse

from django.conf import settings
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


@pytest.fixture
def zip_auth():
    return {
        "HTTP_AUTHORIZATION": "Basic "
        + b64encode(b":" + settings.ZIP_DOWNLOAD_AUTH_TOKEN.encode()).decode()
    }


@pytest.mark.django_db
def test_zip_download_licenses(authenticated_client, random_images_with_licenses):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/", {"query": ""}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/",
        data={"token": token[0]},
        HTTP_AUTHORIZATION="Basic "
        + b64encode(b":" + settings.ZIP_DOWNLOAD_AUTH_TOKEN.encode()).decode(),
    )
    assert r.status_code == 200, r.json()

    assert any("CC-0" in result["url"] for result in r.json()["results"])
    assert any("CC-BY" in result["url"] for result in r.json()["results"])
    assert not any("CC-BY-NC" in result["url"] for result in r.json()["results"])


@pytest.mark.django_db
def test_zip_download_listing(authenticated_client, zip_auth, random_images_with_licenses):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/", data={"token": token[0], "limit": 1}, **zip_auth
    )
    assert r.status_code == 200, r.json()
    # the first page is size 5 (1 limit + 1 metadata + 1 attribution + 2 licenses)
    assert len(r.json()["results"]) == 5, r.json()
    assert r.json()["next"], r.json()

    r = authenticated_client.get(r.json()["next"], **zip_auth)
    assert r.status_code == 200, r.json()
    assert len(r.json()["results"]) == 1, r.json()
    assert not r.json()["next"], r.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ["endpoint", "use_auth_token"],
    [
        ("/api/v2/zip-download/file-listing/", True),
        ("/api/v2/zip-download/file-listing/", False),
        ("/api/v2/zip-download/metadata-file/", True),
        ("/api/v2/zip-download/metadata-file/", False),
        ("/api/v2/zip-download/attribution-file/", True),
        ("/api/v2/zip-download/attribution-file/", False),
    ],
)
def test_zip_download_authentication(
    endpoint, use_auth_token, zip_auth, authenticated_client, random_images_with_licenses
):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    if use_auth_token:
        kwargs = zip_auth
    else:
        kwargs = {}

    r = authenticated_client.get(endpoint, data={"token": token[0]}, **kwargs)
    if use_auth_token:
        assert r.status_code == 200, r.content
    else:
        assert r.status_code == 401, r.content
