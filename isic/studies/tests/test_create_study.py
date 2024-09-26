from django.urls.base import reverse
import pytest

from isic.studies.models import Study


@pytest.mark.django_db()
def test_create_study(
    user,
    authenticated_client,
    collection_factory,
    image_factory,
    question,
    django_capture_on_commit_callbacks,
):
    collection = collection_factory(creator=user)
    collection.images.set([image_factory(public=True) for _ in range(10)])

    with django_capture_on_commit_callbacks(execute=True):
        authenticated_client.post(
            reverse("study-create"),
            {
                "name": "foobar",
                "description": "-",
                "collection": collection.pk,
                "attribution": "some institution",
                "annotators": user.profile.hash_id,
                "public": False,
                "official-INITIAL_FORMS": 0,
                "official-TOTAL_FORMS": 1,
                "official-MAX_NUM_FORMS": "",
                "official-0-question_id": question.pk,
                "official-0-required": True,
                "custom-INITIAL_FORMS": 0,
                "custom-TOTAL_FORMS": 1,
                "custom-MAX_NUM_FORMS": "",
                "custom-0-prompt": "A Custom Question",
                "custom-0-choices": "choice1\nchoice2",
                "custom-0-required": True,
            },
        )
    assert Study.objects.count() == 1
    study = Study.objects.first()
    assert study.name == "foobar"
    assert study.description == "-"
    assert study.collection == collection
    assert study.attribution == "some institution"
    assert not study.public
    assert study.questions.count() == 2
    assert study.tasks.count() == 10
