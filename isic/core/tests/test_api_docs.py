import re

from django.urls import resolve, reverse
import pytest


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_openapi_schema_documents_existing_routes(client):
    r = client.get(reverse("api:openapi-json"))
    assert r.status_code == 200
    schema = r.json()
    assert schema["paths"]

    for path_template, operations in schema["paths"].items():
        path = re.sub(r"\{\w+\}", "1", path_template)
        assert resolve(path).namespace == "api", path_template

        for method in operations:
            r = client.generic(method.upper(), path)
            assert r.status_code != 405, (method, path_template)


@pytest.mark.django_db
def test_swagger(client):
    r = client.get(reverse("docs-swagger"))
    assert r.status_code == 200
    assert reverse("api:openapi-json") in r.content.decode()
