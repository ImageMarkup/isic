import json

from django.conf import settings
from django.test import override_settings
import pytest


@pytest.mark.django_db
def test_csp_reporting_headers_when_configured(client):
    with override_settings(DJANGO_ISIC_SENTRY_CSP_REPORT_URL="https://example.com/csp-report"):
        response = client.get("/")

        assert "Reporting-Endpoints" in response.headers
        assert (
            response.headers["Reporting-Endpoints"]
            == f'csp-endpoint="{settings.DJANGO_ISIC_SENTRY_CSP_REPORT_URL}"'
        )

        assert "Report-To" in response.headers
        report_to = json.loads(response.headers["Report-To"])
        assert report_to["group"] == "csp-endpoint"
        assert report_to["endpoints"][0]["url"] == settings.DJANGO_ISIC_SENTRY_CSP_REPORT_URL
