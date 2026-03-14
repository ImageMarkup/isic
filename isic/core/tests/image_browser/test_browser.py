from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images


@pytest.mark.playwright
def test_collection_picker_dropdown_filter_select_and_keyboard(
    page, collection_factory, image_factory
):
    collections = [collection_factory(public=True, pinned=True) for _ in range(3)]
    # The picker sorts alphabetically by name
    collections.sort(key=lambda c: c.name)

    # Create images and assign them to specific collections so we can verify
    # that filtering by collection shows only the correct images.
    img_in_second = image_factory(public=True)
    collection_add_images(collection=collections[1], image=img_in_second)
    img_in_third = image_factory(public=True)
    collection_add_images(collection=collections[2], image=img_in_third)
    img_unaffiliated = image_factory(public=True)

    page.goto(reverse("core/image-browser"))

    picker_input = page.get_by_placeholder("Type or select collections...")

    # Clicking the input opens the dropdown showing all 3 collections
    picker_input.click()
    for c in collections:
        expect(page.get_by_text(c.name, exact=True)).to_be_visible()

    # Type the first few characters of a collection name to filter
    first = collections[0]
    prefix = first.name[:5]
    picker_input.fill(prefix)
    expect(page.get_by_text(first.name, exact=True)).to_be_visible()

    # Click the first collection to select it -- a chip should appear
    page.get_by_text(first.name, exact=True).click()
    expect(page.get_by_text(first.name, exact=True)).to_be_visible()

    # The selected collection is excluded from the dropdown. Reopen and clear to show
    # only the 2 unselected collections.
    picker_input.click()
    picker_input.fill("")
    for c in collections[1:]:
        expect(page.get_by_text(c.name, exact=True)).to_be_visible()

    # Close dropdown so we can interact with the chip area below it
    page.keyboard.press("Escape")

    # Remove the chip by clicking its X button
    page.get_by_text(first.name, exact=True).locator("..").get_by_role("button").click()

    # Reopen the dropdown -- all 3 collections should appear since nothing is selected
    picker_input.click()
    picker_input.fill("")
    for c in collections:
        expect(page.get_by_text(c.name, exact=True)).to_be_visible()
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    second = collections[1]
    expect(page.get_by_text(second.name, exact=True)).to_be_visible()

    # ArrowDown past the last item clamps to the end -- pressing Enter selects it
    third = collections[2]
    picker_input.fill("")
    for _ in range(10):
        page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_text(third.name, exact=True)).to_be_visible()

    # Escape closes the dropdown -- the non-selected collection should no longer be visible
    picker_input.click()
    expect(page.get_by_text(first.name, exact=True)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_text(first.name, exact=True)).not_to_be_visible()

    # Submit the form and verify only images from the selected collections are shown.
    # second and third are selected; first was removed.
    page.get_by_role("button", name="Search").click()
    page.wait_for_load_state("networkidle")

    page_text = page.text_content("body")
    assert img_in_second.isic_id in page_text
    assert img_in_third.isic_id in page_text
    assert img_unaffiliated.isic_id not in page_text

    # The chips survive the round-trip (picker re-initializes from URL params).
    # Each chip contains the name and a close button, distinguishing it from dropdown items.
    second_chip = (
        page.locator("span").filter(has_text=second.name).filter(has=page.get_by_role("button"))
    )
    third_chip = (
        page.locator("span").filter(has_text=third.name).filter(has=page.get_by_role("button"))
    )
    expect(second_chip).to_be_visible()
    expect(third_chip).to_be_visible()


@pytest.mark.playwright
def test_add_to_collection_modal_with_recent_search_and_confirm(
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page = authenticated_page
    user = authenticated_user

    user_collection = collection_factory(creator=user, public=False, locked=False)
    image_factory(public=True)

    page.goto(reverse("core/image-browser"))

    # Open the Actions dropdown and click "Add results to collection"
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Add results to collection").click()

    # The modal appears showing the user's recent collection
    modal_heading = page.get_by_role("heading", name="Add to Collection")
    expect(modal_heading).to_be_visible()
    expect(page.get_by_text(user_collection.name, exact=True).first).to_be_visible()

    # Search for the collection by typing part of its name (debounced 300ms AJAX)
    search_input = page.get_by_placeholder("Type to search...")
    search_query = user_collection.name[:6]
    search_input.fill(search_query)
    expect(page.get_by_role("button", name=user_collection.name)).to_be_visible()

    # Use a mutable action so we can switch between dismiss and accept
    dialog_action = ["dismiss"]

    def handle_dialog(dialog):
        if dialog_action[0] == "dismiss":
            dialog.dismiss()
        else:
            dialog.accept()

    page.on("dialog", handle_dialog)

    # Click the search result -- confirm dialog appears and is dismissed
    page.get_by_role("button", name=user_collection.name).click()
    # The page stays on the image browser and the modal remains open
    expect(modal_heading).to_be_visible()

    # Clear the search to go back to the recent collections view, then accept the dialog
    search_input.fill("")
    dialog_action[0] = "accept"
    expect(page.get_by_text("or choose from recent")).to_be_visible()
    page.get_by_text("or choose from recent").locator("..").get_by_role(
        "button", name=user_collection.name
    ).click()

    # After accepting, the API call triggers and the page redirects to the collection
    page.wait_for_url(f"**{reverse('core/collection-detail', args=[user_collection.pk])}")
