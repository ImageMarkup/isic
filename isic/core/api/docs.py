import json
from pathlib import Path

from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse
import yaml

OPENAPI_SCHEMA = json.dumps(
    yaml.safe_load((Path(__file__).parent / "openapi.yml").read_text())
).encode()


def openapi_schema(request):
    return HttpResponse(OPENAPI_SCHEMA, content_type="application/json")


def swagger(request):
    swagger_settings = {
        "url": reverse("api:openapi-json"),
        "layout": "BaseLayout",
        "deepLinking": True,
    }
    return render(request, "core/swagger.html", {"swagger_settings": swagger_settings})
