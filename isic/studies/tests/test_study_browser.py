from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.core.services.collection.image import add_images_to_collection
from isic.studies.models import Study
from isic.studies.tests.factories import QuestionFactory


@pytest.mark.playwright
def test_study_create_with_official_and_custom_questions(  # noqa: PLR0915
    authenticated_page, authenticated_user, collection_factory, image_factory
):
    page, user = authenticated_page, authenticated_user

    collection = collection_factory(creator=user, locked=False)
    for _ in range(3):
        add_images_to_collection(collection=collection, image=image_factory(public=True))

    official_questions = [QuestionFactory.create(official=True) for _ in range(3)]

    page.goto(reverse("studies/study-create"))

    # Fill in the base form
    study_name = f"Study {collection.name}"
    study_description = f"A study for {collection.name}."
    study_attribution = f"Institution {collection.name}"
    page.get_by_label("Name").fill(study_name)
    page.get_by_label("Description").fill(study_description)
    page.get_by_label("Attribution").fill(study_attribution)
    page.get_by_label("Collection").select_option(str(collection.pk))
    page.get_by_label("Annotators").fill(user.email)
    page.get_by_label("Zoomable").check()

    # -- Official question picker modal --
    page.get_by_text("Add Official Question").click()
    modal = page.get_by_role("dialog")
    expect(modal).to_be_visible()

    # All official questions should be listed
    for q in official_questions:
        expect(modal.get_by_text(q.prompt)).to_be_visible()

    # Filter by typing part of the first question's prompt
    target_question = official_questions[0]
    page.get_by_placeholder("Filter questions").fill(target_question.prompt[:10])

    # Only the matching question should remain visible
    expect(modal.get_by_text(target_question.prompt)).to_be_visible()

    # Click "Use" to add the question
    modal.get_by_role("link", name="Use").first.click()

    # The question should now show "Used" instead of "Use"
    expect(modal.get_by_text("Used")).to_be_visible()

    # Close the modal
    modal.get_by_role("button", name="Close").click()
    expect(modal).not_to_be_visible()

    # The official question should appear in the form with prompt and choices displayed
    expect(page.get_by_text(target_question.prompt).first).to_be_visible()

    # -- Custom question formset --
    page.get_by_text("Add Custom Question").click()

    # Fill in the custom question fields. Use .last because the first match is the
    # hidden empty form template used for cloning.
    custom_prompt = f"Question about {collection.name}?"
    custom_choices = ["Alpha", "Beta", "Gamma"]
    page.get_by_label("Prompt").last.fill(custom_prompt)
    page.get_by_label("Question type").last.select_option("select")
    page.get_by_label("Choices").last.fill("\n".join(custom_choices))

    # Add a second custom question and then remove it
    page.get_by_text("Add Custom Question").click()
    custom_section = page.get_by_text("Add Custom Question").locator("xpath=../..")
    remove_links = custom_section.get_by_role("link", name="Remove")
    expect(remove_links).to_have_count(2)

    remove_links.nth(1).click()
    expect(custom_section.get_by_role("link", name="Remove")).to_have_count(1)

    # Submit the form
    page.get_by_role("button", name="Create Study").click()

    # Should redirect to the study detail page
    page.wait_for_url("**/studies/*/")

    # Verify the study was created with the correct properties
    study = Study.objects.get(name=study_name)
    assert page.url.endswith(reverse("studies/study-detail", args=[study.pk]))
    assert study.description == study_description
    assert study.attribution == study_attribution
    assert study.collection == collection
    assert study.creator == user
    assert study.public is False
    assert study.zoomable is True

    # The collection should be locked after study creation
    collection.refresh_from_db()
    assert collection.locked is True

    # 2 questions: 1 official + 1 custom
    assert study.questions.count() == 2
    assert study.questions.filter(official=True).first() == target_question

    custom_question = study.questions.get(official=False)
    assert custom_question.prompt == custom_prompt
    assert list(custom_question.choices.values_list("text", flat=True).order_by("text")) == sorted(
        custom_choices
    )

    # Study tasks: one per image per annotator
    assert study.tasks.count() == 3

    expect(page.get_by_text(study.name).first).to_be_visible()
