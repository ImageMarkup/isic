from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import collection_add_images
from isic.studies.models import Annotation, Question, QuestionChoice, StudyTask


@pytest.mark.playwright
def test_multiselect_picker_search_select_all_and_submit(
    authenticated_page, authenticated_user, collection_factory, image_factory, study_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(creator=user)
    image = image_factory(public=True)
    collection_add_images(collection=collection, image=image)

    question = Question.objects.create(
        prompt="Select applicable features",
        type=Question.QuestionType.MULTISELECT,
        official=False,
    )
    choice_texts = [
        "Asymmetry",
        "Border irregularity",
        "Color variation",
        "Diameter > 6mm",
        "Evolving",
        "Blue-white veil",
        "Atypical network",
    ]
    for text in choice_texts:
        QuestionChoice.objects.create(question=question, text=text)

    study = study_factory(
        creator=user,
        collection=collection,
        public=False,
        questions=[question],
        questions__required=True,
    )

    task = StudyTask.objects.create(study=study, annotator=user, image=image)

    page.goto(reverse("study-task-detail", args=[task.pk]))

    expect(page.get_by_text("Select applicable features")).to_be_visible()

    # All choices should be visible
    for text in choice_texts:
        expect(page.get_by_text(text, exact=True)).to_be_visible()

    # Initially 0 selected
    expect(page.get_by_text("0 selected")).to_be_visible()

    # Toggle individual checkboxes
    page.get_by_label("Asymmetry").check()
    page.get_by_label("Color variation").check()
    expect(page.get_by_text("2 selected")).to_be_visible()

    # Uncheck one
    page.get_by_label("Asymmetry").uncheck()
    expect(page.get_by_text("1 selected")).to_be_visible()

    # Search to filter choices
    search_input = page.get_by_placeholder("Search options...")
    search_input.fill("Blue")
    expect(page.get_by_text("Blue-white veil", exact=True)).to_be_visible()
    expect(page.get_by_text("Asymmetry", exact=True)).not_to_be_visible()

    # "Select All Visible" should select only the filtered results
    page.get_by_role("button", name="Select All Visible").click()
    expect(page.get_by_text("2 selected")).to_be_visible()

    # Clear search to see all choices again
    search_input.fill("")

    # Clear all selections
    page.get_by_role("button", name="Clear All").click()
    expect(page.get_by_text("0 selected")).to_be_visible()

    # Select specific choices for submission
    page.get_by_label("Border irregularity").check()
    page.get_by_label("Diameter > 6mm").check()
    page.get_by_label("Evolving").check()
    expect(page.get_by_text("3 selected")).to_be_visible()

    # Submit the annotation
    page.get_by_role("button", name="Respond and continue").click()

    # Should redirect to study detail (only 1 task, so study is complete)
    page.wait_for_url(f"**{reverse('study-detail', args=[study.pk])}")
    expect(page.get_by_text("completed all tasks")).to_be_visible()

    # Verify responses in the database
    annotation = Annotation.objects.get(task=task)
    response = annotation.responses.get(question=question)
    selected_pks = response.value["choices"]
    selected_texts = set(
        QuestionChoice.objects.filter(pk__in=selected_pks).values_list("text", flat=True)
    )
    assert selected_texts == {"Border irregularity", "Diameter > 6mm", "Evolving"}
