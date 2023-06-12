from django.contrib.auth.models import User
from django.db import transaction
from django.db.models.query import QuerySet

from isic.core.models.collection import Collection
from isic.core.services.collection import collection_lock
from isic.studies.models import Study, StudyTask


def study_create(
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
        for image_id in study.collection.images.values_list("id", flat=True).iterator():
            for user in users:
                StudyTask.objects.get_or_create(
                    study_id=study.id,
                    annotator_id=user.id,
                    image_id=image_id,
                )
