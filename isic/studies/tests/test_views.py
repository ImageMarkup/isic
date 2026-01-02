from django.urls.base import reverse
from django.utils import timezone
import pytest

from isic.studies.models import Question
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
