from django.urls import reverse
from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
def test_staff_tools_filter(staff_authenticated_page):
    page = staff_authenticated_page
    page.goto(reverse("core/staff-tools"))

    merge_cohorts = page.get_by_role("link", name="Merge Cohorts")
    email_domains = page.get_by_role("link", name="Email Domains")

    expect(merge_cohorts).to_be_visible()
    expect(email_domains).to_be_visible()

    page.get_by_placeholder("Filter tools").fill("merge")

    expect(merge_cohorts).to_be_visible()
    expect(email_domains).not_to_be_visible()
