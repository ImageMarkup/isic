from django.urls.base import reverse
import pytest

from isic.studies.tests.factories import QuestionFactory, ResponseFactory, StudyFactory


@pytest.mark.django_db
def test_study_responses_csv(staff_client) -> None:
    question = QuestionFactory.create()
    study = StudyFactory.create(public=False, questions=[question])
    ResponseFactory.create(annotation__study=study, question=question)
    ResponseFactory.create(annotation__study=study, question=question)

    r = staff_client.get(reverse("study-download-responses", args=[study.pk]))
    assert r.status_code == 200
    assert len(r.content.decode().splitlines()) == 3
