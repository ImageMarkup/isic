from django.core.exceptions import ValidationError
import pytest

from isic.studies.tests.factories import AnnotationFactory, QuestionChoiceFactory


@pytest.mark.django_db
def test_question_choice_modify() -> None:
    question_choice = QuestionChoiceFactory.create()

    question_choice.text += " (modified)"

    question_choice.save(update_fields=["text"])


@pytest.mark.django_db
def test_question_choice_modify_referenced() -> None:
    question_choice = QuestionChoiceFactory.create()

    AnnotationFactory.create(study__questions=[question_choice.question])
    question_choice.text += " (modified)"

    with pytest.raises(ValidationError, match="the question has already been answered"):
        question_choice.save(update_fields=["text"])
