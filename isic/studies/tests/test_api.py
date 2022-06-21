from unittest import TestCase

import pytest

from isic.studies.models import StudyTask


@pytest.fixture
def study_with_images(user_factory, image_factory, collection_factory, study_factory):
    user = user_factory()
    collection = collection_factory(creator=user, public=True)
    images = [image_factory(public=True) for _ in range(2)]
    collection.images.add(*images)
    study = study_factory(creator=user, collection=collection)
    return study, images


@pytest.mark.django_db
def test_set_tasks(api_client, study_with_images, user_factory):
    users = [user_factory() for _ in range(2)]
    study, images = study_with_images
    api_client.force_login(study.creator)

    r = api_client.post(
        f'/api/v2/studies/{study.pk}/set-tasks/',
        [
            {'isic_id': images[0].isic_id, 'user_hash_id_or_email': users[0].profile.hash_id},
            {'isic_id': images[1].isic_id, 'user_hash_id_or_email': users[1].email},
            # bad image
            {'isic_id': 'ISIC_9999999', 'user_hash_id_or_email': users[1].email},
            # bad user
            {'isic_id': images[1].isic_id, 'user_hash_id_or_email': 'FAKEUSER'},
        ],
    )
    assert r.status_code == 200, r.json()
    assert StudyTask.objects.count() == 2

    tasks_actual = list(StudyTask.objects.all().values('study', 'annotator', 'image'))
    tasks_expected = [
        {'study': study.pk, 'annotator': users[0].pk, 'image': images[0].pk},
        {'study': study.pk, 'annotator': users[1].pk, 'image': images[1].pk},
    ]
    for task_actual, task_expected in zip(tasks_actual, tasks_expected):
        TestCase().assertDictEqual(task_actual, task_expected)
