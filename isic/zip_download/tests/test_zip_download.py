from base64 import b64encode
import json
from urllib.parse import ParseResult, parse_qs, urlparse

from django.conf import settings
from django.core.files.storage import storages
import pytest


@pytest.fixture
def _random_images_with_licenses(image_factory):
    image = image_factory(
        accession__short_diagnosis="melanoma",
        public=True,
    )
    image.accession.copyright_license = "CC-0"
    image.accession.save()

    image = image_factory(
        accession__short_diagnosis="nevus",
        public=True,
    )
    # TODO: factory boy overriding doesn't work for subfields of accession__cohort
    image.accession.copyright_license = "CC-BY"
    image.accession.save()


# We can't rely on the ZIP service to be present during all tests (particularly CI),
# so mock the URL. Make this autouse, but it will only apply to this file.
@pytest.fixture(autouse=True)
def mock_zip_download_service_url(settings) -> None:
    settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL = ParseResult(
        scheme="https",
        netloc=":password@example.com:1234",
        path="",
        params="",
        query="",
        fragment="",
    )


@pytest.fixture
def zip_basic_auth():
    return {
        "HTTP_AUTHORIZATION": "Basic "
        + b64encode(b":" + settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL.password.encode()).decode()
    }


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_random_images_with_licenses")
def test_zip_download_licenses(authenticated_client, zip_basic_auth):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/", {"query": ""}, content_type="application/json"
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/",
        data={"token": token[0]},
        **zip_basic_auth,
    )
    assert r.status_code == 200

    output = json.loads(b"".join(r.streaming_content))

    assert any("CC-0" in result["url"] for result in output["files"])
    assert any("CC-BY" in result["url"] for result in output["files"])
    assert not any("CC-BY-NC" in result["url"] for result in output["files"])


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_random_images_with_licenses")
def test_zip_download_listing(authenticated_client, zip_basic_auth):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/",
        data={"token": token[0], "limit": 1},
        **zip_basic_auth,
    )
    output = json.loads(b"".join(r.streaming_content))
    assert r.status_code == 200, output
    # 6 = 2 images + 1 metadata + 1 attribution + 2 licenses
    assert len(output["files"]) == 6


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("_random_images_with_licenses")
def test_zip_download_listing_urls(authenticated_client, zip_basic_auth, image_factory, user):
    # create both public and private images to test URL generation
    private_image = image_factory(public=False)
    public_image = image_factory(public=True)
    # give the current user access to the private image so it's included in the zip listing
    private_image.accession.cohort.contributor.owners.add(user)

    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/",
        data={"token": token[0]},
        **zip_basic_auth,
    )
    output = json.loads(b"".join(r.streaming_content))
    assert r.status_code == 200, output

    files = output["files"]

    public_file = next(f for f in files if public_image.isic_id in f["zipPath"])
    private_file = next(f for f in files if private_image.isic_id in f["zipPath"])

    expected_public_url = storages["sponsored"].unsigned_url(
        public_image.accession.sponsored_blob.name
    )
    expected_private_url = storages["default"].unsigned_url(private_image.accession.blob.name)

    assert public_file["url"] == expected_public_url
    assert private_file["url"] == expected_private_url


@pytest.mark.django_db
@pytest.mark.usefixtures("_random_images_with_licenses")
@pytest.mark.parametrize(
    ("endpoint", "use_zip_auth_token"),
    [
        ("/api/v2/zip-download/metadata-file/", True),
        ("/api/v2/zip-download/metadata-file/", False),
        ("/api/v2/zip-download/attribution-file/", True),
        ("/api/v2/zip-download/attribution-file/", False),
    ],
)
def test_zip_download_authentication(endpoint, use_zip_auth_token, authenticated_client):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    data = {"token": token[0]} if use_zip_auth_token else {}

    r = authenticated_client.get(endpoint, data=data)
    if use_zip_auth_token:
        assert r.status_code == 200, r.content
    else:
        assert r.status_code == 401, r.content
