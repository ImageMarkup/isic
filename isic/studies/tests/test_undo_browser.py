from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import add_images_to_collection
from isic.studies.models import Annotation, Question, QuestionChoice, StudyTask


@pytest.mark.playwright
def test_study_task_undo_after_annotation(
    authenticated_page, authenticated_user, collection_factory, image_factory, study_factory
):
    page = authenticated_page
    user = authenticated_user

    collection = collection_factory(creator=user)
    images = [image_factory(public=True) for _ in range(2)]
    for img in images:
        add_images_to_collection(collection=collection, image=img)

    question = Question.objects.create(
        prompt="Is this benign?", type=Question.QuestionType.SELECT, official=False
    )
    QuestionChoice.objects.create(question=question, text="Yes")
    QuestionChoice.objects.create(question=question, text="No")

    study = study_factory(
        creator=user,
        collection=collection,
        public=False,
        questions=[question],
        questions__required=True,
    )

    tasks = [StudyTask.objects.create(study=study, annotator=user, image=img) for img in images]

    # Navigate to the first task
    page.goto(reverse("studies/study-task-detail", args=[tasks[0].pk]))

    # The form should show the question with radio buttons
    expect(page.get_by_text("Is this benign?")).to_be_visible()
    page.get_by_label("Yes").check()

    # Submit the annotation
    page.get_by_role("button", name="Respond and continue").click()

    # Should redirect to the second task, with an "Undo" toast visible
    page.wait_for_url(f"**{reverse('studies/study-task-detail', args=[tasks[1].pk])}")
    expect(page.get_by_role("link", name="Undo")).to_be_visible()

    # Verify the first task's annotation exists
    assert Annotation.objects.filter(task=tasks[0]).exists()

    # Click Undo
    page.get_by_role("link", name="Undo").click()

    # Should redirect back to the first task (annotation deleted, form visible again)
    page.wait_for_url(f"**{reverse('studies/study-task-detail', args=[tasks[0].pk])}")
    expect(page.get_by_text("Is this benign?")).to_be_visible()
    expect(page.get_by_role("button", name="Respond and continue")).to_be_visible()

    # Verify the annotation was deleted
    assert not Annotation.objects.filter(task=tasks[0]).exists()
