from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images


@pytest.mark.playwright
def test_share_collection_with_multiple_users(
    staff_authenticated_page,
    staff_authenticated_user,
    collection_factory,
    image_factory,
    user_factory,
):
    page = staff_authenticated_page
    staff_user = staff_authenticated_user

    collection = collection_factory(public=False, locked=False, creator=staff_user)
    image = image_factory(public=True)
    collection_add_images(collection=collection, image=image)

    target_a = user_factory()
    target_b = user_factory()

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # Verify nobody is shared with initially
    expect(page.get_by_text("Directly shared with")).to_be_visible()
    expect(page.get_by_text("nobody")).to_be_visible()

    # Open the share modal
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Share").click()

    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    # Search for and select the first user.
    # Use press_sequentially instead of fill because Select2 listens for keyboard
    # events to trigger AJAX searches, and fill() dispatches a single input event
    # that Select2 doesn't reliably handle.
    page.locator(".select2-container").click()
    select2_input = page.locator(".select2-search__field")
    expect(select2_input).to_be_visible()
    select2_input.press_sequentially(target_a.email)
    result_a = page.locator(".select2-results__option", has_text=target_a.email)
    expect(result_a).to_be_visible()
    result_a.click()

    # Search for and select the second user
    page.locator(".select2-container").click()
    select2_input = page.locator(".select2-search__field")
    expect(select2_input).to_be_visible()
    select2_input.press_sequentially(target_b.email)
    result_b = page.locator(".select2-results__option", has_text=target_b.email)
    expect(result_b).to_be_visible()
    result_b.click()

    # Both users should appear as Select2 choices
    expect(page.locator(".select2-selection__choice", has_text=target_a.email)).to_be_visible()
    expect(page.locator(".select2-selection__choice", has_text=target_b.email)).to_be_visible()

    # Uncheck email notifications to avoid slow email sending during teardown
    page.get_by_label("Send email notification to selected users").uncheck()

    # Accept the confirm dialog and share
    page.on("dialog", lambda dialog: dialog.accept())
    modal.get_by_role("button", name="Share collection and images with users").click()

    # Page reloads - verify the flash message and both shared users appear
    expect(page.get_by_text("Sharing collection with user(s)")).to_be_visible()
    expect(page.get_by_text("Directly shared with")).to_be_visible()
    expect(page.get_by_text(target_a.email)).to_be_visible()
    expect(page.get_by_text(target_b.email)).to_be_visible()

    # The "nobody" text should no longer appear
    expect(page.get_by_text("nobody")).not_to_be_visible()

    page.wait_for_timeout(1000)
