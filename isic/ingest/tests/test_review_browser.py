import re

from django.urls import reverse
from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
def test_review_gallery_reject_toggle_and_submit(
    staff_authenticated_page, cohort_factory, accession_factory
):
    page = staff_authenticated_page

    cohort = cohort_factory()
    accessions = [accession_factory(cohort=cohort, ingested=True) for _ in range(3)]

    page.goto(reverse("ingest/cohort-review", args=[cohort.pk]))

    # All 3 accessions should be visible with reject buttons
    reject_buttons = page.get_by_role("button", name="Reject")
    expect(reject_buttons).to_have_count(3)

    # Toggle reject on the first accession -- the button should get the "dim" class
    first_reject = reject_buttons.first
    first_reject.click()
    expect(first_reject).to_have_class(re.compile(r"dim"))

    # Toggle it again -- the dim class should be removed
    first_reject.click()
    expect(first_reject).not_to_have_class(re.compile(r"dim"))

    # Reject the first accession for real this time, leave the others as accept
    first_reject.click()
    expect(first_reject).to_have_class(re.compile(r"dim"))

    # Click "Accept remaining" to submit all reviews
    page.get_by_role("button", name="Accept remaining").click()

    # The page reloads and all accessions are now reviewed
    page.wait_for_load_state("networkidle")
    expect(page.locator("text=No accessions left to review!")).to_be_visible()

    # Verify the database state: first was rejected, others accepted
    accessions[0].refresh_from_db()
    assert accessions[0].review.value is False
    for acc in accessions[1:]:
        acc.refresh_from_db()
        assert acc.review.value is True


@pytest.mark.playwright
def test_review_gallery_accession_modal_and_metadata_tabs(
    staff_authenticated_page, cohort_factory, accession_factory
):
    page = staff_authenticated_page

    cohort = cohort_factory()
    accession = accession_factory(cohort=cohort, ingested=True)

    page.goto(reverse("ingest/cohort-review", args=[cohort.pk]))

    # Click the thumbnail image to open the modal
    page.locator("img").first.click()

    # The modal should appear showing the original filename
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()
    expect(modal.get_by_text(accession.original_blob_name)).to_be_visible()

    # Switch to "Unstructured Metadata" tab
    modal.get_by_role("link", name="Unstructured Metadata").click()
    unstructured_tab = modal.locator("pre").nth(1)
    expect(unstructured_tab).to_be_visible()

    # Switch back to "Metadata" tab
    modal.get_by_role("link", name="Metadata", exact=True).click()
    metadata_tab = modal.locator("pre").first
    expect(metadata_tab).to_be_visible()

    # Close the modal
    modal.get_by_role("button", name="Close").click()
    expect(modal).not_to_be_visible()
