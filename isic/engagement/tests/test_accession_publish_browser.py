from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.models.image import Image


@pytest.mark.playwright
@pytest.mark.usefixtures("_search_index")
def test_engagement_accession_publish(
    staff_authenticated_page, cohort_factory, accession_review_factory, engagement_accession_factory
):
    page = staff_authenticated_page

    accessions = [
        engagement_accession_factory(
            accession=accession_review_factory(
                accession__cohort=cohort_factory(), accession__ingested=True, value=True
            ).accession
        ).accession
        for _ in range(2)
    ]

    page.goto(reverse("engagement/accession-list"))
    page.get_by_role("link", name="Publish 2").click()

    # both cohorts are listed, since each publishes under its own attribution.
    expect(page.get_by_role("row")).to_have_count(len(accessions) + 1)

    # a plain multi <select> has no search box, so this only appears once select2 has built the
    # shared collections field.
    expect(page.get_by_role("searchbox", name="Search")).to_be_visible()

    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Publish 2 accessions").click()

    expect(page.get_by_text("Publishing 2 images")).to_be_visible()
    assert Image.objects.filter(accession__in=accessions).count() == len(accessions)
