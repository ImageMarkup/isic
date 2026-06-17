from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.models.collection import Collection
from isic.core.services.collection.image import add_images_to_collection


@pytest.mark.playwright
def test_collection_picker_dropdown_filter_select_and_keyboard(
    page, collection_factory, image_factory
):
    for _ in range(3):
        collection_factory(public=True, pinned=True)

    # Read the collections back in the picker's display order. The dropdown
    # renders them in the server's order (Postgres `ORDER BY name`).
    collections = list(Collection.objects.pinned().order_by("name"))

    # Create images and assign them to specific collections so we can verify
    # that filtering by collection shows only the correct images.
    img_in_second = image_factory(public=True)
    add_images_to_collection(collection=collections[1], image=img_in_second)
    img_in_third = image_factory(public=True)
    add_images_to_collection(collection=collections[2], image=img_in_third)
    img_unaffiliated = image_factory(public=True)

    page.goto(reverse("core/image-browser"))

    picker = page.get_by_role("combobox")
    first, second, third = collections

    # Clicking the input opens the dropdown showing all 3 collections
    picker.click()
    for c in collections:
        expect(page.get_by_role("option", name=c.name)).to_be_visible()

    # Type the first few characters of a collection name to filter
    picker.fill(first.name[:5])
    expect(page.get_by_role("option", name=first.name)).to_be_visible()

    # Click the first collection to select it -- a badge should appear
    page.get_by_role("option", name=first.name).click()
    expect(page.get_by_role("listitem").filter(has_text=first.name)).to_be_visible()

    # The selected collection is excluded from the dropdown, showing only the 2 unselected.
    for c in [second, third]:
        expect(page.get_by_role("option", name=c.name)).to_be_visible()

    # Close dropdown so we can interact with the badge area below it
    page.keyboard.press("Escape")

    # Remove the badge by clicking its close button
    page.get_by_role("button", name=f"Remove {first.name}").click()

    # Reopen the dropdown -- all 3 collections should appear since nothing is selected
    picker.click()
    for c in collections:
        expect(page.get_by_role("option", name=c.name)).to_be_visible()

    # Keyboard: ArrowDown twice then Enter selects the second collection
    page.keyboard.press("ArrowDown")
    page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("listitem").filter(has_text=second.name)).to_be_visible()

    # ArrowDown past the last item clamps to the end -- pressing Enter selects it
    for _ in range(10):
        page.keyboard.press("ArrowDown")
    page.keyboard.press("Enter")
    expect(page.get_by_role("listitem").filter(has_text=third.name)).to_be_visible()

    # Escape closes the dropdown -- the non-selected collection should no longer be visible
    picker.click()
    expect(page.get_by_role("option", name=first.name)).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.get_by_role("option", name=first.name)).not_to_be_visible()

    # Submit the form and verify only images from the selected collections are shown.
    # second and third are selected; first was removed.
    page.get_by_role("button", name="Search", exact=True).click()
    page.wait_for_load_state("networkidle")

    page_text = page.text_content("body")
    assert img_in_second.isic_id in page_text
    assert img_in_third.isic_id in page_text
    assert img_unaffiliated.isic_id not in page_text

    # The badges survive the round-trip (picker re-initializes from URL params).
    # The dropdown is closed after page load, so the names are only visible as badges.
    expect(page.get_by_role("listitem").filter(has_text=second.name)).to_be_visible()
    expect(page.get_by_role("listitem").filter(has_text=third.name)).to_be_visible()


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
    page.get_by_role("button", name="Add results to collection").click()

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
