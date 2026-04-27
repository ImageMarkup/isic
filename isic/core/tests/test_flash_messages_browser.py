from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import add_images_to_collection


@pytest.mark.playwright
def test_add_images_to_collection_shows_flash_message(
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page = authenticated_page
    user = authenticated_user

    user_collection = collection_factory(creator=user, public=False, locked=False)
    image_factory(public=True)

    page.goto(reverse("core/image-browser"))

    # Open the "Add results to collection" modal
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Add results to collection").click()

    # Accept the confirm dialog when it appears
    page.on("dialog", lambda dialog: dialog.accept())

    # Select the collection from the recent section
    expect(page.get_by_text("or choose from recent")).to_be_visible()
    page.get_by_text("or choose from recent").locator("..").get_by_role(
        "button", name=user_collection.name
    ).click()

    # Should redirect to collection detail with the flash message
    page.wait_for_url(f"**{reverse('core/collection-detail', args=[user_collection.pk])}")
    expect(page.get_by_text("Adding images to collection")).to_be_visible()


@pytest.mark.playwright
def test_image_removal_shows_flash_message(
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(public=True, locked=False, creator=user)
    images = [image_factory(public=True) for _ in range(2)]
    for img in images:
        add_images_to_collection(collection=collection, image=img)

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # Enter removal mode, toggle one image, and remove it
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("menuitem", name="Remove Images").click()

    page.get_by_text(images[0].isic_id).locator("..").get_by_role("button", name="Remove").click()

    page.on("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name="Abort").locator("..").get_by_role(
        "button", name="Remove"
    ).click()

    # Should redirect to collection detail with a flash message about removal
    page.wait_for_url(f"**{reverse('core/collection-detail', args=[collection.pk])}")
    expect(page.get_by_text("Removed 1 images")).to_be_visible()


@pytest.mark.playwright
def test_study_creation_shows_flash_message(
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(creator=user, locked=False)
    add_images_to_collection(collection=collection, image=image_factory(public=True))

    page.goto(reverse("studies/study-create"))

    page.get_by_label("Name").fill(f"Study {collection.name}")
    page.get_by_label("Description").fill(f"Description for {collection.name}")
    page.get_by_label("Attribution").fill(f"Attribution {collection.name}")
    page.get_by_label("Collection").select_option(str(collection.pk))
    page.get_by_label("Annotators").fill(user.email)

    page.get_by_role("button", name="Create Study").click()

    # Should redirect to study detail with a flash message
    page.wait_for_url("**/studies/*/")
    expect(page.get_by_text("Creating study, this may take a few minutes.")).to_be_visible()
