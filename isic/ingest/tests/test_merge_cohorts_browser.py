from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images
from isic.ingest.models import Cohort


@pytest.mark.playwright
def test_merge_cohorts_autocomplete_preview_and_submit(
    staff_authenticated_page,
    cohort_factory,
    accession_factory,
    image_factory,
    collection_factory,
):
    page = staff_authenticated_page

    # Create two cohorts with accessions
    collection_a = collection_factory()
    cohort_a = cohort_factory(collection=collection_a)
    accession_a = accession_factory(cohort=cohort_a)
    image_a = image_factory(accession=accession_a, public=True)
    collection_add_images(collection=collection_a, image=image_a)

    collection_b = collection_factory()
    cohort_b = cohort_factory(collection=collection_b)
    accession_b = accession_factory(cohort=cohort_b)
    image_b = image_factory(accession=accession_b, public=True)
    collection_add_images(collection=collection_b, image=image_b)

    page.goto(reverse("merge-cohorts"))

    expect(page.get_by_text("Merge Cohorts").first).to_be_visible()

    # Type in the first autocomplete field to search for cohort_a
    first_input = page.locator("input[name='autocomplete_cohort']")
    first_input.press_sequentially(cohort_a.name[:5], delay=50)

    # Wait for autocomplete results and select cohort_a
    first_result = page.get_by_text(cohort_a.name, exact=True).first
    expect(first_result).to_be_visible()
    first_result.click()

    # Preview should show cohort details
    expect(page.get_by_text(cohort_a.description).first).to_be_visible()

    # Type in the second autocomplete field to search for cohort_b
    second_input = page.locator("input[name='autocomplete_cohort_to_merge']")
    second_input.press_sequentially(cohort_b.name[:5], delay=50)

    # Wait for autocomplete results and select cohort_b
    second_result = page.get_by_text(cohort_b.name, exact=True).first
    expect(second_result).to_be_visible()
    second_result.click()

    # Preview should show cohort_b details
    expect(page.get_by_text(cohort_b.description).first).to_be_visible()

    # Submit the merge
    page.get_by_role("button", name="Merge Cohorts").click()

    # Should redirect to cohort_a detail page with success flash message
    page.wait_for_url(f"**{reverse('cohort-detail', args=[cohort_a.pk])}")
    expect(page.get_by_text("Cohort merged successfully.")).to_be_visible()

    # Verify cohort_b was deleted and its accessions moved to cohort_a
    assert not Cohort.objects.filter(pk=cohort_b.pk).exists()
    assert cohort_a.accessions.count() == 2
