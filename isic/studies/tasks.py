from celery import shared_task
from django.db import transaction

from isic.studies.models import Study, StudyTask


@shared_task
def populate_study_tasks_task(study_pk: int, user_pks: list[int]):
    study = Study.objects.prefetch_related('collection__images').get(pk=study_pk)

    with transaction.atomic():
        for image_pk in study.collection.images.values_list('pk', flat=True):
            for user_pk in user_pks:
                StudyTask.objects.create(
                    study_id=study_pk,
                    annotator_id=user_pk,
                    image_id=image_pk,
                )
