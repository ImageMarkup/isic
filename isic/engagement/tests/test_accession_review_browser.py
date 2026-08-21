from django.urls import reverse
from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
def test_engagement_accession_review(
    staff_authenticated_page, cohort_factory, accession_factory, engagement_accession_factory
):
    page = staff_authenticated_page

    accessions = [
        engagement_accession_factory(
            accession=accession_factory(cohort=cohort_factory(), ingested=True)
        ).accession
        for _ in range(2)
    ]

    page.goto(reverse("engagement/accession-list"))
    page.get_by_role("link", name="Review", exact=True).click()

    # both cohorts' accessions are reviewable from the one gallery.
    reject_buttons = page.get_by_role("button", name="Reject")
    expect(reject_buttons).to_have_count(len(accessions))

    reject_buttons.first.click()
    page.get_by_role("button", name="Accept remaining").click()

    page.wait_for_load_state("networkidle")
    expect(page.locator("text=No accessions left to review!")).to_be_visible()

    for accession in accessions:
        accession.refresh_from_db()

    assert {accession.review.value for accession in accessions} == {True, False}
