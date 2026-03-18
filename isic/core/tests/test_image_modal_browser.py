import io

from django.urls import reverse
from PIL import Image as PILImage
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images


def _make_jpeg_bytes(width, height, color="red"):
    img = PILImage.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


IMAGE_SIZES = [
    pytest.param((100, 100), id="small-square"),
    pytest.param((300, 1200), id="tall-portrait"),
    pytest.param((2000, 400), id="wide-landscape"),
    pytest.param((1500, 1500), id="large-square"),
]

VIEWPORT_SIZES = [
    pytest.param({"width": 375, "height": 667}, id="mobile"),
    pytest.param({"width": 768, "height": 1024}, id="tablet"),
    pytest.param({"width": 1280, "height": 720}, id="desktop"),
    pytest.param({"width": 1920, "height": 1080}, id="wide"),
]


@pytest.mark.playwright
@pytest.mark.parametrize("image_size", IMAGE_SIZES)
@pytest.mark.parametrize("viewport", VIEWPORT_SIZES)
def test_image_modal_fits_viewport(
    new_context,
    live_server,
    collection_factory,
    image_factory,
    image_size,
    viewport,
):
    w, h = image_size

    collection = collection_factory(public=True, pinned=True)
    image = image_factory(
        public=True,
        accession__width=w,
        accession__height=h,
    )
    collection_add_images(collection=collection, image=image)

    # MinIO URLs aren't browser-accessible in the test environment,
    # so intercept image requests and serve valid JPEGs directly.
    blob_bytes = _make_jpeg_bytes(w, h)
    thumb_bytes = _make_jpeg_bytes(256, 256)

    ctx = new_context(base_url=live_server.url, viewport=viewport)
    ctx.set_default_timeout(15_000)
    page = ctx.new_page()

    page.route(
        image.blob.url,
        lambda route: route.fulfill(content_type="image/jpeg", body=blob_bytes),
    )
    page.route(
        image.thumbnail_256.url,
        lambda route: route.fulfill(content_type="image/jpeg", body=thumb_bytes),
    )

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    # Hover the thumbnail first (triggers hovered=true which loads the full image URL),
    # then click to open the modal.
    thumb_el = page.locator("img").first
    thumb_el.hover()
    thumb_el.click()
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    # Wait for the full-size image to actually render
    modal_img = modal.locator("img")
    modal_img.wait_for(state="visible")
    page.wait_for_function(
        "el => el.naturalWidth > 0 && el.complete",
        arg=modal_img.element_handle(),
    )

    box = modal.bounding_box()
    assert box is not None, "Modal dialog has no bounding box"
    assert box["x"] >= 0, f"Modal left edge ({box['x']}) is off-screen"
    assert box["y"] >= 0, f"Modal top edge ({box['y']}) is off-screen"
    assert box["x"] + box["width"] <= viewport["width"], (
        f"Modal right edge ({box['x'] + box['width']}) exceeds viewport width ({viewport['width']})"
    )
    assert box["y"] + box["height"] <= viewport["height"], (
        f"Modal bottom edge ({box['y'] + box['height']}) "
        f"exceeds viewport height ({viewport['height']})"
    )
