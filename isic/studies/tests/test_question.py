from django.core.exceptions import ValidationError
import pytest

from isic.studies.tests.factories import AnnotationFactory, QuestionFactory


@pytest.mark.django_db
def test_question_modify_referenced() -> None:
    question = QuestionFactory.create()

    AnnotationFactory.create(study__questions=[question])
    question.prompt += " (modified)"

    with pytest.raises(ValidationError, match="it has already been answered"):
        question.save(update_fields=["prompt"])
