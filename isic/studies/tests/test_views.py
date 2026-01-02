from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.factories import UserFactory
from isic.studies.models import Question, Response
from isic.studies.models.question_choice import QuestionChoice
from isic.studies.tests.factories import (
    AnnotationFactory,
    QuestionFactory,
    ResponseFactory,
    StudyFactory,
    StudyTaskFactory,
)


@pytest.mark.django_db
def test_study_responses_csv(staff_client) -> None:
    question = QuestionFactory.create()
    study = StudyFactory.create(public=False, questions=[question])
    ResponseFactory.create(annotation__study=study, question=question)
    ResponseFactory.create(annotation__study=study, question=question)

    r = staff_client.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200
    assert len(r.content.decode().splitlines()) == 3


@pytest.mark.django_db
def test_study_responses_csv_number_question(staff_client) -> None:
    question = QuestionFactory.create(type=Question.QuestionType.NUMBER, choices=[])
    study = StudyFactory.create(public=False, questions=[question])
    annotation = AnnotationFactory.create(study=study)
    annotation.responses.create(question=question, value=42.5)

    r = staff_client.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200
    lines = r.content.decode().splitlines()
    assert len(lines) == 2
    assert "42.5" in lines[1]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("input_value", "expected_value"),
    [
        ("42", 42),
        ("42.5", 42.5),
        ("0", 0),
        ("-5", -5),
        ("-3.14", -3.14),
    ],
)
def test_study_task_detail_post_number_question(client, input_value, expected_value):
    question = QuestionFactory.create(type=Question.QuestionType.NUMBER, choices=[])
    study = StudyFactory.create(
        questions=[question],
        questions__required=True,
    )

    study_task = StudyTaskFactory.create(study=study)
    user = study_task.annotator
    client.force_login(user)
    client.post(
        reverse("study-task-detail", args=[study_task.pk]),
        {"start_time": timezone.now(), question.pk: input_value},
    )
    assert study_task.annotation

    response = study_task.annotation.responses.first()
    assert response.annotation.annotator == user
    assert response.question == question
    assert response.choice is None
    assert response.value == expected_value
    assert type(response.value) is type(expected_value)


@pytest.mark.django_db
def test_study_add_annotators(client, django_capture_on_commit_callbacks, image_factory):
    study_task = StudyTaskFactory.create()
    study = study_task.study
    study.collection.images.add(image_factory())
    new_user = UserFactory.create()

    client.force_login(study.creator)
    with django_capture_on_commit_callbacks(execute=True):
        r = client.post(
            reverse("study-add-annotators", args=[study.pk]),
            {"annotators": new_user.email},
        )
    assert r.status_code == 302

    assert study.tasks.filter(annotator=new_user).exists()


@pytest.mark.django_db
def test_multiselect_question_response_and_export(staff_client) -> None:
    question = QuestionFactory.create(
        type=Question.QuestionType.MULTISELECT,
        choices=[],
    )
    choice1 = QuestionChoice.objects.create(question=question, text="Option A")
    QuestionChoice.objects.create(question=question, text="Option B")
    choice3 = QuestionChoice.objects.create(question=question, text="Option C")

    study = StudyFactory.create(public=False, questions=[question])
    annotation = AnnotationFactory.create(study=study)

    Response.objects.create(
        annotation=annotation,
        question=question,
        value={"choices": [choice1.pk, choice3.pk]},
    )

    r = staff_client.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200
    lines = r.content.decode().splitlines()
    assert len(lines) == 2
    assert "Option A|Option C" in lines[1]


@pytest.mark.django_db
def test_multiselect_question_empty_response(staff_client) -> None:
    question = QuestionFactory.create(
        type=Question.QuestionType.MULTISELECT,
        choices=[],
    )
    QuestionChoice.objects.create(question=question, text="Option A")

    study = StudyFactory.create(public=False, questions=[question])
    annotation = AnnotationFactory.create(study=study)

    Response.objects.create(
        annotation=annotation,
        question=question,
        value={"choices": []},
    )

    r = staff_client.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200
    lines = r.content.decode().splitlines()
    assert len(lines) == 2
    assert lines[1].endswith(",")
