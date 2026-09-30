from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.models.collection import CollectionTag


@pytest.mark.playwright
def test_collection_create_with_new_tags(staff_authenticated_page):
    page = staff_authenticated_page
    page.goto(reverse("core/collection-create"))
    expect(page.locator("#tags-select")).to_be_visible()
    expect(page.locator("#tags-select-hidden")).not_to_be_visible()

    name = "My New Collection"
    tags = ["test", "fake"]
    page.get_by_label("Name").fill(name)
    combobox = page.get_by_role("combobox")
    for t in tags:
        combobox.fill(t)
        combobox.press("Enter")

    page.get_by_role("button", name="Create Collection").click()
    page.wait_for_url("**/collections/*/")
    expect(page.locator(".heading-1")).to_have_text(name)
    for t in tags:
        expect(page.locator(".rounded-full").filter(has_text=t)).to_be_visible()
    assert CollectionTag.objects.count() == 2


@pytest.mark.playwright
def test_collection_edit_tags_select_existing(
    staff_authenticated_page, staff_authenticated_user, collection_factory
):
    tag = "test"
    CollectionTag.objects.create(tag=tag)
    collection = collection_factory(
        public=True, pinned=False, locked=False, creator=staff_authenticated_user
    )

    page = staff_authenticated_page
    page.goto(reverse("core/collection-edit", args=[collection.pk]))
    combobox = page.get_by_role("combobox")
    combobox.fill(tag[:2])  # type a few letters to match exising tag
    combobox.press("Enter")

    page.get_by_role("button", name="Save").click()
    page.wait_for_url("**/collections/*/")
    expect(page.locator(".rounded-full").filter(has_text=tag)).to_be_visible()


@pytest.mark.playwright
def test_collection_edit_delete_tag(
    staff_authenticated_page, staff_authenticated_user, collection_factory
):
    tag_to_delete = "deleteme"
    tags = ["test", "fake", tag_to_delete]
    collection = collection_factory(
        public=True, pinned=False, locked=False, creator=staff_authenticated_user
    )
    collection.tags.set(CollectionTag.objects.bulk_create([CollectionTag(tag=t) for t in tags]))
    collection.save()

    page = staff_authenticated_page
    page.goto(reverse("core/collection-edit", args=[collection.pk]))

    # deselect tag first so it appears in options menu
    page.get_by_text(tag_to_delete).get_by_role("button").click()

    # open options menu
    combobox = page.get_by_role("combobox")
    combobox.click()

    # click trash can icon
    page.locator(".ri-delete-bin-line").click()

    # check confirm/cancel buttons visible, click confirm delete
    cancel_button = page.get_by_role("button", name="Cancel")
    expect(cancel_button).to_be_visible()
    delete_button = page.get_by_role("button", name="Delete")
    expect(delete_button).to_be_visible()
    delete_button.click()

    page.wait_for_url("**/collections/edit/*/")
    expect(page.get_by_text("Collection Tag deleted successfully.")).to_be_visible()

    page.goto(reverse("core/collection-detail", args=[collection.pk]))
    for t in tags:
        tag_chip = page.locator(".rounded-full").filter(has_text=t)
        if t == tag_to_delete:
            expect(tag_chip).not_to_be_visible()
        else:
            expect(tag_chip).to_be_visible()


@pytest.mark.playwright
def test_collection_list_filter_by_tag(
    staff_authenticated_page, staff_authenticated_user, collection_factory
):
    tag = "test"
    collections = [
        collection_factory(
            public=True, pinned=False, locked=False, creator=staff_authenticated_user
        )
        for i in range(5)
    ]
    collections[0].tags.set([CollectionTag.objects.create(tag=tag)])

    page = staff_authenticated_page
    page.goto(reverse("core/collection-list", query={"exclude_empty": 0}))
    expect(page.locator("tbody tr")).to_have_count(len(collections))

    combobox = page.get_by_role("combobox", name="Select tags")
    combobox.fill(tag)
    combobox.press("Enter")

    page.wait_for_url(f"**/collections/?*tags={tag}")
    expect(page.locator("tbody tr")).to_have_count(1)
