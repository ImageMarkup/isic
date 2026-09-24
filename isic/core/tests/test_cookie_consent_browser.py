from cookie_consent.models import CookieGroup
from django.urls import reverse
from playwright.sync_api import expect
import pytest


@pytest.fixture
def analytics_cookie_group():
    # live_server tests flush the database, which removes the group the migration creates.
    return CookieGroup.objects.get_or_create(varname="analytics", defaults={"name": "Analytics"})[0]


@pytest.mark.playwright
@pytest.mark.usefixtures("analytics_cookie_group")
def test_analytics_loads_only_after_consent(page):
    analytics_requests = []

    def _record_and_abort(route):
        analytics_requests.append(route.request.url)
        route.abort()

    page.route("https://www.googletagmanager.com/**", _record_and_abort)

    banner = page.get_by_text("We use cookies to understand how the Archive is used.")

    page.goto(reverse("core/collection-list"))
    expect(banner).to_be_visible()
    assert analytics_requests == []

    page.get_by_role("button", name="Decline").click()
    page.wait_for_url(f"**{reverse('core/collection-list')}")
    expect(banner).not_to_be_visible()

    page.reload()
    expect(banner).not_to_be_visible()
    assert analytics_requests == []

    page.goto(reverse("cookie_consent_cookie_group_list"))
    expect(page.get_by_text("Declined")).to_be_visible()
    with page.expect_request("https://www.googletagmanager.com/**"):
        page.get_by_role("button", name="Accept").click()
    expect(page.get_by_text("Accepted")).to_be_visible()

    with page.expect_request("https://www.googletagmanager.com/**"):
        page.goto(reverse("core/collection-list"))
    expect(banner).not_to_be_visible()
