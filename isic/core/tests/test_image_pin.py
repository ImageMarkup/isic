from django.urls import reverse
from playwright.sync_api import expect
import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "expected_status"),
    [
        (lf("client"), 403),
        (lf("authenticated_client"), 403),
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


@pytest.mark.parametrize("pin_sort", [True, False])
@pytest.mark.django_db
def test_images_pagination_prevent_switch_ordering(image_factory, authenticated_client, pin_sort):
    images = [image_factory(public=True, pinned=(i % 2 == 0)) for i in range(10)]
    if pin_sort:
        expected_ids = [images[i].isic_id for i in [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]]
    else:
        expected_ids = [image.isic_id for image in images]

    # Apply pin sort to first request
    query = {"limit": 5}
    if pin_sort:
        query["pin_sort"] = True
    r = authenticated_client.get(reverse("api:image_list"), data=query).json()
    result_ids = [image.get("isic_id") for image in r.get("results")]
    assert result_ids == expected_ids[0:5]

    # Switch pin sort on next request
    next_url = r.get("next")
    if pin_sort:
        next_url = next_url.replace("&pin_sort=True", "")
    else:
        next_url += "&pin_sort=True"

    # pin sort switch should be ignored, continue with initial ordering
    r = authenticated_client.get(next_url).json()
    result_ids = [image.get("isic_id") for image in r.get("results")]
    assert result_ids == expected_ids[5:10]


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
