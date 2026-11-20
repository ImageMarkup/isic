from urllib.parse import urlencode

from django.core.signing import TimestampSigner
from django.urls import reverse
import pytest

FILES = {
    "file-listing": "api:zip_download_listing",
    "metadata-file": "api:zip_download_metadata_file",
    "attribution-file": "api:zip_download_attribution_file",
}
# collections and users are named by their manifest key
SEARCHES = {
    "medium_collection": {"user": None, "query": "", "collections": ["medium"]},
    "malignant": {"user": None, "query": "diagnosis_1:Malignant", "collections": None},
    "all_public": {"user": None, "query": "", "collections": None},
    "everything_as_staff": {"user": "staff", "query": "", "collections": None},
}


@pytest.mark.parametrize("search", SEARCHES)
@pytest.mark.parametrize("file", FILES)
def test_zip_download(benchmark_with_memory, endpoint, manifest, file, search):
    """Request the files the zip server needs for a download."""
    token = dict(SEARCHES[search])
    if token["user"]:
        token["user"] = manifest["users"][token["user"]]
    if token["collections"]:
        token["collections"] = [manifest["collections"][key] for key in token["collections"]]
    query = urlencode({"token": TimestampSigner().sign_object(token)})
    benchmark_with_memory(endpoint("anonymous", f"{reverse(FILES[file])}?{query}"))
