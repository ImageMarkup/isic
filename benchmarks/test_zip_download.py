from urllib.parse import urlencode

from django.core.signing import TimestampSigner
from django.urls import reverse
import pytest

FILES = {
    "file-listing": "api:zip_download_listing",
    "metadata-file": "api:zip_download_metadata_file",
    "attribution-file": "api:zip_download_attribution_file",
}
# collections are named by their manifest key
SEARCHES = {
    "medium_collection": {"query": "", "collections": ["medium"]},
    "malignant": {"query": "diagnosis_1:Malignant", "collections": None},
    "all_public": {"query": "", "collections": None},
}


@pytest.mark.parametrize("search", SEARCHES)
@pytest.mark.parametrize("file", FILES)
def test_zip_download(benchmark_with_memory, endpoint, manifest, file, search):
    """Request the files the zip server needs for an anonymous download."""
    token = {"user": None, **SEARCHES[search]}
    if token["collections"]:
        token["collections"] = [manifest["collections"][key] for key in token["collections"]]
    query = urlencode({"token": TimestampSigner().sign_object(token)})
    benchmark_with_memory(endpoint("anonymous", f"{reverse(FILES[file])}?{query}"))
