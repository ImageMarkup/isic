import itertools

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.query import QuerySet

from isic.core.models.collection import Collection
from isic.core.services.collection import collection_lock
from isic.studies.models import Study, StudyTask


def study_create(  # noqa: PLR0913
    *,
    creator: User,
    owners,
    attribution: str,
    name: str,
    description: str,
    collection: Collection,
    public: bool,
) -> Study:
    study = Study(
        creator=creator,
        attribution=attribution,
        name=name,
        description=description,
        collection=collection,
        public=public,
    )
    study.full_clean()

    with transaction.atomic():
        study.save()
        study.owners.set(owners)
        collection_lock(collection=collection)

    return study


def study_update(*, study: Study, **fields):
    for field, value in fields.items():
        setattr(study, field, value)

    study.full_clean()

    return study.save()


def populate_study_tasks(*, study: Study, users: QuerySet[User]) -> None:
    with transaction.atomic():
        for user_image_batch in itertools.batched(
            itertools.product(
                users.values_list("id", flat=True),
                study.collection.images.values_list("id", flat=True),
            ),
            1_000,
        ):
            tasks = []
            for user, image in user_image_batch:
                tasks.append(
                    StudyTask(
                        study_id=study.id,
                        annotator_id=user,
                        image_id=image,
                    )
                )

            StudyTask.objects.bulk_create(tasks, ignore_conflicts=True)
