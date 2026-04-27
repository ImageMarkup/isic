import pathlib

from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images
from isic.studies.models import Question, QuestionChoice, StudyTask

_TEST_IMAGE = pathlib.Path(__file__).parent.parent.parent / "ingest/tests/data/ISIC_0000000.jpg"


@pytest.mark.playwright
def test_study_task_image_is_zoomable(
    authenticated_page, authenticated_user, collection_factory, image_factory, study_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(creator=user)
    image = image_factory(public=True)
    collection_add_images(collection=collection, image=image)

    question = Question.objects.create(
        prompt="Is this benign?", type=Question.QuestionType.SELECT, official=False
    )
    QuestionChoice.objects.create(question=question, text="Yes")

    study = study_factory(
        creator=user,
        collection=collection,
        public=False,
        questions=[question],
        questions__required=True,
        zoomable=True,
    )

    task = StudyTask.objects.create(study=study, annotator=user, image=image)

    # Serve the local test JPEG for any image request so the OL viewer can load
    # the image regardless of whether the Minio URL is reachable from the browser.
    page.route("**/*.jpg", lambda route: route.fulfill(path=str(_TEST_IMAGE)))

    page.goto(reverse("studies/study-task-detail", args=[task.pk]))

    # Click the study image to open the full-screen modal; mouseenter fires first
    # (setting hovered=true), then the click fires (setting open=true).
    page.locator("img.max-w-full.h-auto").click()

    # The zoomable viewer container (512x512) is visible at the top of the modal.
    viewer = page.locator(f"#image-{image.pk}")
    expect(viewer).to_be_visible()

    # OpenLayers renders a <canvas> inside the viewer container once the image loads.
    # Check this while the viewer is still at the top of the dialog (before scrolling).
    expect(viewer.locator("canvas")).to_be_visible()

    # The hint text confirms the zoom viewer is shown instead of a plain <img>.
    hint = page.get_by_text("Scroll to zoom, click and drag to pan")
    expect(hint).to_be_visible()
