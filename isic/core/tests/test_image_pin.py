from django.urls import reverse
from playwright.sync_api import expect
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.tests.factories import data_dir


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "expected_status"),
    [
        (lf("client"), 401),
        (lf("authenticated_client"), 401),
        (lf("staff_client"), 200),
    ],
    ids=["anonymous", "authenticated", "staff"],
)
def test_core_api_image_set_pinned_permissions(client_, expected_status, image_factory):
    image = image_factory(public=True)
    r = client_.post(
        reverse("api:image_set_pinned", kwargs={"id": image.pk}),
        {"pinned": True},
        content_type="application/json",
    )
    assert r.status_code == expected_status

    image.refresh_from_db()
    if expected_status == 200:
        assert image.pinned == 1
    else:
        assert image.pinned == 0


@pytest.mark.django_db
def test_core_api_image_set_pinned_private_image_rejected(staff_client, image_factory):
    image = image_factory(public=False)
    r = staff_client.post(
        reverse("api:image_set_pinned", kwargs={"id": image.pk}),
        {"pinned": True},
        content_type="application/json",
    )
    assert r.status_code == 400
    image.refresh_from_db()
    assert image.pinned == 0


@pytest.mark.django_db
def test_core_api_image_sort_by_pinned(image_factory, authenticated_client):
    image_1 = image_factory(public=True)
    image_2 = image_factory(public=True, pinned=1)

    # List endpoint
    r = authenticated_client.get(reverse("api:image_list"), data={"pin_sort": True})
    ordered_ids = [image.get("isic_id") for image in r.json().get("results")]
    assert ordered_ids == [image_2.isic_id, image_1.isic_id]

    # Search endpoint
    r = authenticated_client.get(reverse("api:image_search"), data={"pin_sort": True})
    ordered_ids = [image.get("isic_id") for image in r.json().get("results")]
    assert ordered_ids == [image_2.isic_id, image_1.isic_id]


@pytest.mark.playwright
def test_image_pin_unpin(image_factory, staff_authenticated_page):
    page = staff_authenticated_page
    image_id = image_factory(public=True).isic_id
    page.goto(reverse("core/image-detail", args=[image_id]))

    # Pin the image
    page.get_by_role("button", name="Actions").click()
    page.get_by_role("button", name="Pin image").click()
    page.wait_for_url(f"**{reverse('core/image-detail', args=[image_id])}")
    expect(page.get_by_text("image pinned.")).to_be_visible()

    # Unpin button should now be present
    page.get_by_role("button", name="Actions").click()
    expect(page.get_by_role("button", name="Unpin image")).to_be_visible()

    # Unpin the image
    page.get_by_role("button", name="Unpin image").click()
    page.wait_for_url(f"**{reverse('core/image-detail', args=[image_id])}")
    expect(page.get_by_text("image unpinned.")).to_be_visible()

    # Pin button should be back
    page.get_by_role("button", name="Actions").click()
    expect(page.get_by_role("button", name="Pin image")).to_be_visible()


@pytest.mark.playwright
def test_image_pin_disabled_when_private(image_factory, staff_authenticated_page):
    page = staff_authenticated_page
    image_id = image_factory(public=False).isic_id
    page.goto(reverse("core/image-detail", args=[image_id]))

    page.get_by_role("button", name="Actions").click()
    pin_button = page.get_by_role("button", name="Pin image")
    expect(pin_button).to_be_disabled()
    expect(pin_button).to_have_accessible_description("Only public images can be pinned")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "expected_status"),
    [
        (lf("client"), 401),
        (lf("authenticated_client"), 401),
        (lf("staff_client"), 200),
    ],
    ids=["anonymous", "authenticated", "staff"],
)
def test_core_api_image_reorder_pins(client_, expected_status, image_factory):
    images = [
        image_factory(public=True),
        image_factory(public=True, pinned=1),
        image_factory(public=True, pinned=2),
    ]
    expected_order = [
        images[2].isic_id,
        images[1].isic_id,
        images[0].isic_id,
    ]

    r = client_.get(reverse("api:image_list"), data={"pin_sort": True})
    assert [image.get("isic_id") for image in r.json().get("results")] == expected_order

    r = client_.post(
        reverse("api:image_pins_reorder"),
        {"order": [images[1].isic_id, images[2].isic_id]},
        content_type="application/json",
    )
    assert r.status_code == expected_status

    if expected_status == 200:
        expected_order = [
            images[1].isic_id,
            images[2].isic_id,
            images[0].isic_id,
        ]

    r = client_.get(reverse("api:image_list"), data={"pin_sort": True})
    assert [image.get("isic_id") for image in r.json().get("results")] == expected_order


@pytest.mark.django_db
def test_core_api_image_reorder_pins_invalid_id(staff_client):
    r = staff_client.post(
        reverse("api:image_pins_reorder"),
        {"order": ["foo"]},
        content_type="application/json",
    )
    assert r.status_code == 400


@pytest.mark.playwright
def test_image_pins_reorder_drag(staff_authenticated_page, image_factory):
    page = staff_authenticated_page
    # distinct thumbnail sources make the swap easier to view when running headed
    first = image_factory(
        public=True,
        pinned=2,
        accession__sponsored_thumbnail_256_blob__from_path=data_dir / "ISIC_0000001.jpg",
    )
    second = image_factory(
        public=True,
        pinned=1,
        accession__sponsored_thumbnail_256_blob__from_path=data_dir / "ISIC_0000002.jpg",
    )

    page.goto(reverse("core/image-pins"))
    items = page.locator("#image-grid > div")
    expect(items).to_have_count(2)

    save_button = page.get_by_role("button", name="Save")
    expect(save_button).to_be_disabled()

    # drag the first image onto the second. sortable tracks intermediate mouse
    # moves, so a single jump to the target isn't enough to register the swap.
    target = items.nth(1).bounding_box()
    items.nth(0).hover()
    page.mouse.down()
    page.mouse.move(target["x"] + target["width"] / 2, target["y"] + target["height"] / 2, steps=10)
    page.mouse.up()

    expect(save_button).to_be_enabled()
    save_button.click()

    # saving reloads the page, so the new order and the message come from the server
    expect(page.get_by_text("Reordered pinned images.")).to_be_visible()
    expect(items.nth(0).get_by_role("link", name=second.isic_id)).to_be_visible()
    expect(items.nth(1).get_by_role("link", name=first.isic_id)).to_be_visible()
