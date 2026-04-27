from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import add_images_to_collection


@pytest.mark.playwright
def test_collection_detail_lazy_attribution_and_share_modal(
    staff_authenticated_page,
    staff_authenticated_user,
    collection_factory,
    image_factory,
    user_factory,
):
    page = staff_authenticated_page
    staff_user = staff_authenticated_user

    collection = collection_factory(public=False, locked=False, creator=staff_user)
    images = [image_factory(public=True) for _ in range(3)]
    for img in images:
        add_images_to_collection(collection=collection, image=img)

    share_target = user_factory()

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # -- Lazy attribution loading --
    attribution_section = page.get_by_text("Attribution").locator("..")
    attribution_link = attribution_section.get_by_role("link", name="View")
    expect(attribution_link).to_be_visible()

    attribution_link.click()

    # After clicking, attribution data should load and display
    attribution_list = attribution_section.locator("ul li")
    expect(attribution_list.first).to_be_visible()

    # The "View" link should be hidden after fetching
    expect(attribution_link).not_to_be_visible()

    # -- Share modal --
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Share").click()

    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    # Select2 should be initialized - type in the search to find the target user.
    # Use press_sequentially instead of fill because Select2 listens for keyboard
    # events to trigger AJAX searches, and fill() dispatches a single input event
    # that Select2 doesn't reliably handle.
    page.locator(".select2-container").click()
    select2_input = page.locator(".select2-search__field")
    expect(select2_input).to_be_visible()
    select2_input.press_sequentially(share_target.email)

    # Wait for the AJAX results to appear and select the user
    select2_result = page.locator(".select2-results__option", has_text=share_target.email)
    expect(select2_result).to_be_visible()
    select2_result.click()

    # The user should appear in the Select2 selection
    expect(page.locator(".select2-selection__choice", has_text=share_target.email)).to_be_visible()

    # Uncheck email notifications to avoid slow email sending during teardown
    page.get_by_label("Send email notification to selected users").uncheck()

    # Handle the confirm dialog and share
    page.on("dialog", lambda dialog: dialog.accept())
    modal.get_by_role("button", name="Share collection and images with users").click()

    # Page reloads after sharing - verify the shared user appears
    expect(page.get_by_text("Directly shared with")).to_be_visible()
    expect(page.get_by_text(share_target.email)).to_be_visible()

    # The share triggers a page reload via window.location.reload(). The WSGI handler's
    # post-response cleanup (close_old_connections) runs in the server thread and can race
    # with test teardown's database flush. Wait briefly to let the server finish.
    page.wait_for_timeout(1000)


@pytest.mark.playwright
def test_collection_detail_image_removal(
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(public=True, locked=False, creator=user)
    images = [image_factory(public=True) for _ in range(3)]
    for img in images:
        add_images_to_collection(collection=collection, image=img)

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # Enter image removal mode via the Actions menu
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Remove Images").click()

    # The removal mode alert should be visible
    expect(page.get_by_text("images pending removal")).to_be_visible()

    # Toggle the first two images for removal
    first_image = images[0]
    second_image = images[1]

    page.get_by_text(first_image.isic_id).locator("..").get_by_role("button", name="Remove").click()
    page.get_by_text(second_image.isic_id).locator("..").get_by_role(
        "button", name="Remove"
    ).click()

    # The pending count should now show 2
    expect(page.get_by_text("2 images pending removal")).to_be_visible()

    # Un-toggle the second image
    page.get_by_text(second_image.isic_id).locator("..").get_by_role(
        "button", name="Remove"
    ).click()

    # Handle the confirm dialog and click the bulk "Remove" button in the alert bar.
    # Use the Abort button as anchor since it's unique on the page and sits next to Remove.
    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Abort").locator("..").get_by_role(
        "button", name="Remove"
    ).click()

    # Page redirects to the collection detail (without removal mode)
    page.wait_for_url(f"**{reverse('core/collection-detail', args=[collection.pk])}")

    # Only the first image should have been removed
    page_text = page.text_content("body")
    assert first_image.isic_id not in page_text
    assert second_image.isic_id in page_text
    assert images[2].isic_id in page_text

    # Verify in the database
    assert collection.images.count() == 2
