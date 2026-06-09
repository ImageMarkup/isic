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
        assert image.pinned is None


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
    image_id = image_factory().isic_id
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
