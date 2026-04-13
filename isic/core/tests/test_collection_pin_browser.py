from django.urls import reverse
from playwright.sync_api import expect
import pytest


@pytest.mark.playwright
def test_collection_pin_unpin(
    staff_authenticated_page,
    staff_authenticated_user,
    collection_factory,
):
    page = staff_authenticated_page

    collection = collection_factory(
        public=True, pinned=False, locked=False, creator=staff_authenticated_user
    )
    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # Pin icon should not be visible yet
    expect(page.locator(".ri-pushpin-2-fill")).not_to_be_visible()

    # Pin the collection
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Pin Collection").click()

    page.wait_for_url(f"**{reverse('core/collection-detail', args=[collection.pk])}")

    expect(page.get_by_text("Collection pinned.")).to_be_visible()
    expect(page.locator(".ri-pushpin-2-fill")).to_be_visible()

    # Unpin button should now be present
    page.get_by_role("button", name="Actions").click()
    expect(page.get_by_role("menuitem", name="Unpin Collection")).to_be_visible()

    # Unpin the collection
    page.get_by_role("menuitem", name="Unpin Collection").click()

    page.wait_for_url(f"**{reverse('core/collection-detail', args=[collection.pk])}")

    expect(page.get_by_text("Collection unpinned.")).to_be_visible()
    expect(page.locator(".ri-pushpin-2-fill")).not_to_be_visible()

    # Pin button should be back
    page.get_by_role("button", name="Actions").click()
    expect(page.get_by_role("menuitem", name="Pin Collection")).to_be_visible()


@pytest.mark.playwright
def test_collection_pin_disabled_for_private_collection(
    staff_authenticated_page,
    staff_authenticated_user,
    collection_factory,
):
    page = staff_authenticated_page

    collection = collection_factory(
        public=False, pinned=False, locked=False, creator=staff_authenticated_user
    )
    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    page.get_by_role("button", name="Actions").click()

    # The disabled span should be present with the correct title
    pin_item = page.locator("span", has_text="Pin Collection")
    expect(pin_item).to_be_visible()
    expect(pin_item).to_have_attribute("title", "Collection must be public to be pinned")

    # No clickable link — only the disabled span exists
    expect(page.locator("a", has_text="Pin Collection")).not_to_be_visible()
