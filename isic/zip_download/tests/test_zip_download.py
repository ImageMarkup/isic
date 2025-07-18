from base64 import b64encode
import json
from urllib.parse import ParseResult, parse_qs, urlparse

from django.conf import settings
from django.core.signing import TimestampSigner
from ninja.errors import AuthenticationError
import pytest

from isic.core.models import Image


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


@pytest.mark.django_db
def test_zip_api_auth(mocker, authenticated_client, zip_basic_auth):
    from isic.zip_download.api import zip_api_auth

    token = TimestampSigner().sign_object({"token": "foo"})

    request = mocker.MagicMock(
        headers={"Authorization": "Basic " + b64encode(b":badcredentials").decode()}
    )
    with pytest.raises(AuthenticationError):
        zip_api_auth(request)

    request = mocker.MagicMock(
        headers={"Authorization": zip_basic_auth["HTTP_AUTHORIZATION"]},
        GET={"token": token},
    )
    assert zip_api_auth(request)

    request = mocker.MagicMock(
        headers={"Authorization": zip_basic_auth["HTTP_AUTHORIZATION"]}, GET={"token": "badtoken"}
    )
    assert not zip_api_auth(request)


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
def test_zip_download_listing_wildcard_urls(
    authenticated_client, zip_basic_auth, settings, image_factory, mocker, user
):
    # create a private image to ensure wildcard urls are only present for private images
    image = image_factory(public=False)
    # give the current user access to the image so it's included in the zip listing
    image.accession.cohort.contributor.owners.add(user)

    r = authenticated_client.post(
        "/api/v2/zip-download/url/",
        {"query": ""},
        content_type="application/json",
    )
    assert r.status_code == 200, r.json()
    parsed_url = urlparse(r.json())
    token = parse_qs(parsed_url.query)["zsid"]

    # Mock the CloudFrontSigner to return a predictable signature
    settings.ISIC_ZIP_DOWNLOAD_WILDCARD_URLS = True

    mock_storage = mocker.MagicMock()
    mock_storage.cloudfront_key_id = "test"
    mock_storage.custom_domain = "test.test"
    mocker.patch("isic.zip_download.api.default_storage", mock_storage)

    mocker.patch("isic.zip_download.api._cloudfront_signer", return_value="testsigner")
    mocked_signer = mocker.MagicMock()
    mocked_signer.generate_presigned_url = (
        lambda url, policy: f"{url}?PretendPolicy=foo"  # noqa: ARG005
    )
    mocker.patch("isic.zip_download.api.CloudFrontSigner", return_value=mocked_signer)

    r = authenticated_client.get(
        "/api/v2/zip-download/file-listing/",
        data={"token": token[0]},
        **zip_basic_auth,
    )
    output = json.loads(b"".join(r.streaming_content))
    assert r.status_code == 200, output

    urls = [file["url"] for file in output["files"]]

    for image in Image.objects.all():
        if image.public:
            assert any(url.endswith(image.blob.name) for url in urls)
        else:
            assert (
                f"https://{mock_storage.custom_domain}/{image.blob.name}?PretendPolicy=foo" in urls
            )


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
