from base64 import b64encode
from urllib.parse import parse_qs, urlparse

from django.conf import settings
import pytest

from isic.core.models import Image


@pytest.fixture
def random_images_with_licenses(image_factory):
    image = image_factory(
        accession__diagnosis="melanoma",
        public=True,
    )
    image.accession.copyright_license = "CC-0"
    image.accession.save()

    image = image_factory(
        accession__diagnosis="nevus",
        public=True,
    )
    # TODO: factory boy overriding doesn't work for subfields of accession__cohort
    image.accession.copyright_license = "CC-BY"
    image.accession.save()


@pytest.fixture
def zip_basic_auth():
    return {
        "HTTP_AUTHORIZATION": "Basic "
        + b64encode(b":" + settings.ZIP_DOWNLOAD_BASIC_AUTH_TOKEN.encode()).decode()
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
        + b64encode(b":" + settings.ZIP_DOWNLOAD_BASIC_AUTH_TOKEN.encode()).decode(),
    )
    assert r.status_code == 200, r.json()

    assert any("CC-0" in result["url"] for result in r.json()["files"])
    assert any("CC-BY" in result["url"] for result in r.json()["files"])
    assert not any("CC-BY-NC" in result["url"] for result in r.json()["files"])


@pytest.mark.django_db
def test_zip_download_listing(authenticated_client, zip_basic_auth, random_images_with_licenses):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/", data={"token": token[0], "limit": 1}, **zip_basic_auth
    )
    assert r.status_code == 200, r.json()
    # 6 = 2 images + 1 metadata + 1 attribution + 2 licenses
    assert len(r.json()["files"]) == 6, r.json()


@pytest.mark.django_db
def test_zip_download_listing_wildcard_urls(
    authenticated_client, zip_basic_auth, random_images_with_licenses, settings, mocker
):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    # Mock the CloudFrontSigner to return a predictable signature
    settings.ZIP_DOWNLOAD_WILDCARD_URLS = True
    settings.AWS_CLOUDFRONT_KEY_ID = "test"
    settings.AWS_S3_CUSTOM_DOMAIN = "test.test"
    mocker.patch("isic.zip_download.api._cloudfront_signer", return_value="testsigner")
    mocked_signer = mocker.MagicMock()
    mocked_signer.generate_presigned_url = lambda url, policy: f"{url}?PretendPolicy=foo"
    mocker.patch("isic.zip_download.api.CloudFrontSigner", return_value=mocked_signer)

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/", data={"token": token[0], "limit": 1}, **zip_basic_auth
    )
    assert r.status_code == 200, r.json()

    for image in Image.objects.all():
        assert any(
            file["url"].endswith(f"{image.accession.blob.name}?PretendPolicy=foo")
            for file in r.json()["files"]
        )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ["endpoint", "use_zip_auth_token"],
    [
        ("/api/v2/zip-download/metadata-file/", True),
        ("/api/v2/zip-download/metadata-file/", False),
        ("/api/v2/zip-download/attribution-file/", True),
        ("/api/v2/zip-download/attribution-file/", False),
    ],
)
def test_zip_download_authentication(
    endpoint, use_zip_auth_token, authenticated_client, random_images_with_licenses
):
    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    if use_zip_auth_token:
        data = {"token": token[0]}
    else:
        data = {}

    r = authenticated_client.get(endpoint, data=data)
    if use_zip_auth_token:
        assert r.status_code == 200, r.content
    else:
        assert r.status_code == 401, r.content
