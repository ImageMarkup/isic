import io

from django.test import Client
from django.urls import reverse
from PIL import Image as PILImage
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images
from isic.studies.models import Question, QuestionChoice, StudyTask


def _make_jpeg_bytes(width, height, color="red"):
    img = PILImage.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _intercept_image_urls(page, urls):
    for url, jpeg_bytes in urls:

        def _fulfill(body):
            def _handler(route, *_args):
                route.fulfill(content_type="image/jpeg", body=body)

            return _handler

        page.route(url, _fulfill(jpeg_bytes))


def _assert_modal_fits_viewport(modal, viewport):
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
def test_collection_detail_image_modal_fits_viewport(
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

    blob_bytes = _make_jpeg_bytes(w, h)
    thumb_bytes = _make_jpeg_bytes(256, 256)

    ctx = new_context(base_url=live_server.url, viewport=viewport)
    ctx.set_default_timeout(15_000)
    page = ctx.new_page()

    _intercept_image_urls(
        page,
        [
            (image.blob.url, blob_bytes),
            (image.thumbnail_256.url, thumb_bytes),
        ],
    )

    page.goto(reverse("core/collection-detail", args=[collection.pk]))

    thumb_el = page.locator("img").first
    thumb_el.hover()
    thumb_el.click()
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    modal_img = modal.locator("img")
    expect(modal_img).to_be_visible()
    expect(modal_img).to_have_js_property("complete", value=True)

    _assert_modal_fits_viewport(modal, viewport)


@pytest.mark.playwright
@pytest.mark.parametrize("image_size", IMAGE_SIZES)
@pytest.mark.parametrize("viewport", VIEWPORT_SIZES)
def test_accession_modal_fits_viewport(
    new_context,
    live_server,
    staff_authenticated_user,
    cohort_factory,
    accession_factory,
    image_size,
    viewport,
):
    w, h = image_size

    cohort = cohort_factory()
    accession = accession_factory(cohort=cohort, ingested=True, width=w, height=h)

    blob_bytes = _make_jpeg_bytes(w, h)
    thumb_bytes = _make_jpeg_bytes(256, 256)

    ctx = new_context(base_url=live_server.url, viewport=viewport)
    ctx.set_default_timeout(15_000)
    page = ctx.new_page()

    client = Client()
    client.force_login(staff_authenticated_user)
    session_cookie = client.cookies["sessionid"]
    ctx.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie.value,
                "url": live_server.url,
            }
        ]
    )

    _intercept_image_urls(
        page,
        [
            (accession.blob_.url, blob_bytes),
            (accession.thumbnail_.url, thumb_bytes),
        ],
    )

    page.goto(reverse("cohort-review", args=[cohort.pk]))

    thumb_el = page.locator("img").first
    thumb_el.hover()
    thumb_el.click()
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    modal_img = modal.locator("img")
    expect(modal_img).to_be_visible()
    expect(modal_img).to_have_js_property("complete", value=True)

    _assert_modal_fits_viewport(modal, viewport)


@pytest.mark.playwright
@pytest.mark.parametrize("image_size", IMAGE_SIZES)
@pytest.mark.parametrize("viewport", VIEWPORT_SIZES)
def test_study_task_image_modal_fits_viewport(
    new_context,
    live_server,
    authenticated_user,
    collection_factory,
    image_factory,
    study_factory,
    image_size,
    viewport,
):
    w, h = image_size

    collection = collection_factory(creator=authenticated_user)
    image = image_factory(public=True, accession__width=w, accession__height=h)
    collection_add_images(collection=collection, image=image)

    question = Question.objects.create(
        prompt="Diagnosis?", type=Question.QuestionType.SELECT, official=False
    )
    QuestionChoice.objects.create(question=question, text="Choice A")

    study = study_factory(
        creator=authenticated_user,
        collection=collection,
        public=False,
        questions=[question],
        zoomable=True,
    )

    task = StudyTask.objects.create(study=study, annotator=authenticated_user, image=image)

    blob_bytes = _make_jpeg_bytes(w, h)
    thumb_bytes = _make_jpeg_bytes(256, 256)

    ctx = new_context(base_url=live_server.url, viewport=viewport)
    ctx.set_default_timeout(15_000)
    page = ctx.new_page()

    client = Client()
    client.force_login(authenticated_user)
    session_cookie = client.cookies["sessionid"]
    ctx.add_cookies(
        [
            {
                "name": "sessionid",
                "value": session_cookie.value,
                "url": live_server.url,
            }
        ]
    )

    _intercept_image_urls(
        page,
        [
            (image.blob.url, blob_bytes),
            (image.thumbnail_256.url, thumb_bytes),
        ],
    )

    page.goto(reverse("studies/study-task-detail", args=[task.pk]))

    # The study task page shows the full image directly (not a thumbnail),
    # click it to open the modal.
    page.locator("img").first.hover()
    page.locator("img").first.click()
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    # The study task modal shows the OL zoom viewer (not a plain img).
    viewer = modal.locator(f"#image-{image.pk}")
    expect(viewer).to_be_visible()

    _assert_modal_fits_viewport(modal, viewport)
