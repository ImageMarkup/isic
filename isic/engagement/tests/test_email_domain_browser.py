from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.engagement.models import EmailDomainContributor


@pytest.mark.playwright
def test_email_domain_add_with_autocomplete(staff_authenticated_page, contributor_factory):
    page = staff_authenticated_page
    contributor = contributor_factory()
    domain = "mskcc.org"

    page.goto(reverse("engagement/email-domain-list"))

    page.get_by_role("textbox").first.fill(domain)

    fieldset = page.get_by_role("group").filter(has_text="Contributor")
    fieldset.get_by_role("searchbox").press_sequentially(contributor.institution_name[:5], delay=50)

    result = fieldset.get_by_text(contributor.institution_name, exact=True).first
    expect(result).to_be_visible()
    result.click()

    # the preview panel confirms the selection resolved to a real contributor
    expect(fieldset.get_by_text(contributor.institution_url).first).to_be_visible()

    page.get_by_role("button", name="Add Email Domain").click()

    expect(page.get_by_text("Email domain added successfully.")).to_be_visible()
    expect(page.get_by_role("cell", name=domain)).to_be_visible()
    expect(page.get_by_role("cell", name=contributor.institution_name)).to_be_visible()

    email_domain = EmailDomainContributor.objects.get()
    assert email_domain.domain == domain
    assert email_domain.contributor == contributor
