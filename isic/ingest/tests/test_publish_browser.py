from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.ingest.models import AccessionStatus


@pytest.fixture
def publishable_cohort(user_factory, cohort_factory, accession_review_factory):
    staff_user = user_factory(is_staff=True)
    cohort = cohort_factory(creator=staff_user, contributor__creator=staff_user)
    accession_review_factory(
        accession__cohort=cohort,
        accession__status=AccessionStatus.SUCCEEDED,
        accession__blob_size=1,
        accession__width=1,
        accession__height=1,
        creator=staff_user,
        value=True,
    )
    return cohort


@pytest.mark.playwright
def test_cohort_publish(staff_authenticated_page, publishable_cohort):
    page = staff_authenticated_page
    cohort = publishable_cohort

    page.goto(reverse("upload/cohort-publish", args=[cohort.pk]))

    expect(page.get_by_text("There are 1 accessions that can be published")).to_be_visible()

    page.get_by_label("Make images public").check()

    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Publish 1 accessions").click()

    page.wait_for_url(f"**{reverse('ingest/cohort-detail', args=[cohort.pk])}")
    expect(page.get_by_text("Publishing 1 image")).to_be_visible()


@pytest.mark.playwright
def test_cohort_publish_with_additional_collections(
    staff_authenticated_page,
    publishable_cohort,
    collection_factory,
    user_factory,
):
    page = staff_authenticated_page
    cohort = publishable_cohort

    other_user = user_factory()
    extra_collection_a = collection_factory(creator=other_user, public=False, locked=False)
    extra_collection_b = collection_factory(creator=other_user, public=False, locked=False)

    page.goto(reverse("upload/cohort-publish", args=[cohort.pk]))

    expect(page.get_by_text("There are 1 accessions that can be published")).to_be_visible()

    # Select the first additional collection via Select2.
    # Use press_sequentially instead of fill because Select2 listens for keyboard
    # events to trigger AJAX searches, and fill() dispatches a single input event
    # that Select2 doesn't reliably handle.
    page.locator(".select2-container").click()
    select2_input = page.locator(".select2-search__field")
    expect(select2_input).to_be_visible()
    select2_input.press_sequentially(extra_collection_a.name[:5])

    result_a = page.locator(".select2-results__option", has_text=extra_collection_a.name)
    expect(result_a).to_be_visible()
    result_a.click()

    expect(
        page.locator(".select2-selection__choice", has_text=extra_collection_a.name)
    ).to_be_visible()

    # Select the second additional collection
    page.locator(".select2-container").click()
    select2_input = page.locator(".select2-search__field")
    expect(select2_input).to_be_visible()
    select2_input.press_sequentially(extra_collection_b.name[:5])

    result_b = page.locator(".select2-results__option", has_text=extra_collection_b.name)
    expect(result_b).to_be_visible()
    result_b.click()

    expect(
        page.locator(".select2-selection__choice", has_text=extra_collection_b.name)
    ).to_be_visible()

    # Submit with confirmation dialog
    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Publish 1 accessions").click()

    page.wait_for_url(f"**{reverse('ingest/cohort-detail', args=[cohort.pk])}")
    expect(page.get_by_text("Publishing 1 image")).to_be_visible()
