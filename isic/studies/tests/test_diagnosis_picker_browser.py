from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import add_images_to_collection
from isic.studies.models import Question, QuestionChoice, Response, StudyTask


@pytest.mark.playwright
def test_diagnosis_picker_search_expand_select_and_submit(
    authenticated_page, authenticated_user, collection_factory, image_factory, study_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(creator=user)
    image = image_factory(public=True)
    add_images_to_collection(collection=collection, image=image)

    # Create a diagnosis question with hierarchical choices
    question = Question.objects.create(
        prompt="What is the diagnosis?", type=Question.QuestionType.DIAGNOSIS, official=False
    )
    choices = {}
    for path in [
        "Benign:Nevus:Blue Nevus",
        "Benign:Nevus:Junctional",
        "Benign:Nevus:Compound",
        "Benign:Dermatofibroma",
        "Malignant:Melanoma:Superficial Spreading",
        "Malignant:Melanoma:Nodular",
        "Malignant:Basal Cell Carcinoma",
    ]:
        choices[path] = QuestionChoice.objects.create(question=question, text=path)

    study = study_factory(
        creator=user,
        collection=collection,
        public=False,
        questions=[question],
        questions__required=True,
    )

    task = StudyTask.objects.create(study=study, annotator=user, image=image)

    page.goto(reverse("studies/study-task-detail", args=[task.pk]))

    # The picker should be visible with its search input and heading
    expect(page.get_by_role("heading", name="Recent Diagnoses")).to_be_visible()
    search_input = page.get_by_placeholder("Search diagnoses...")
    expect(search_input).to_be_visible()

    # The top-level nodes should be visible: Benign, Malignant.
    # Wait for the tree toggle arrows to appear, which indicates JS has finished
    # building the tree and hiding child nodes.
    expect(page.get_by_text("Benign", exact=True)).to_be_visible()
    expect(page.get_by_text("Malignant", exact=True)).to_be_visible()
    expect(page.locator(".tree-toggle", has_text="\u25b6").first).to_be_visible()

    # Child nodes should be hidden initially
    expect(page.get_by_text("Nevus", exact=True)).not_to_be_visible()

    # Expand "Benign" by clicking its toggle
    page.get_by_text("Benign", exact=True).locator("xpath=preceding-sibling::span").click()
    expect(page.get_by_text("Nevus", exact=True)).to_be_visible()
    expect(page.get_by_text("Dermatofibroma", exact=True)).to_be_visible()

    # Expand "Nevus"
    page.get_by_text("Nevus", exact=True).locator("xpath=preceding-sibling::span").click()
    expect(page.get_by_text("Blue Nevus", exact=True)).to_be_visible()

    # Collapse "Benign"
    page.get_by_text("Benign", exact=True).locator("xpath=preceding-sibling::span").click()
    expect(page.get_by_text("Nevus", exact=True)).not_to_be_visible()

    # -- Search filtering --
    search_input.fill("Nodular")

    # Only the matching path should be visible: Malignant > Melanoma > Nodular
    expect(page.get_by_text("Nodular", exact=True)).to_be_visible()
    expect(page.get_by_text("Melanoma", exact=True)).to_be_visible()
    expect(page.get_by_text("Malignant", exact=True)).to_be_visible()

    # Non-matching nodes should be hidden
    expect(page.get_by_text("Benign", exact=True)).not_to_be_visible()
    expect(page.get_by_text("Basal Cell Carcinoma", exact=True)).not_to_be_visible()

    # Clear search
    search_input.fill("")

    # All top-level nodes should be visible again
    expect(page.get_by_text("Benign", exact=True)).to_be_visible()
    expect(page.get_by_text("Malignant", exact=True)).to_be_visible()

    # -- Select a diagnosis via search --
    search_input.fill("Junctional")
    junctional = page.get_by_text("Junctional", exact=True)
    expect(junctional).to_be_visible()
    junctional.click()

    # Selection indicator should appear
    expect(page.get_by_text("Selected:")).to_be_visible()
    expect(page.get_by_text("Benign:Nevus:Junctional")).to_be_visible()

    # Submit the annotation
    page.get_by_role("button", name="Respond and continue").click()

    # Should redirect to the study detail page (no more tasks)
    page.wait_for_url(f"**{reverse('studies/study-detail', args=[study.pk])}")

    # Verify the response was saved in the database
    response = Response.objects.get(annotation__study=study, annotation__annotator=user)
    assert response.choice == choices["Benign:Nevus:Junctional"]
    assert response.question == question
