from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query import QuerySet

from isic.studies.models import Study, StudyTask


def study_update(*, study: Study, **fields):
    for field, value in fields.items():
        setattr(study, field, value)

    if study.public and not study.collection.public:
        raise ValidationError("Can't make a study public with a private collection.")

    study.full_clean()

    return study.save()


def populate_study_tasks(*, study: Study, users: QuerySet[User]) -> None:
    with transaction.atomic():
        for image_id in study.collection.images.values_list('id', flat=True).iterator():
            for user in users:
                StudyTask.objects.get_or_create(
                    study_id=study.id,
                    annotator_id=user.id,
                    image_id=image_id,
                )
