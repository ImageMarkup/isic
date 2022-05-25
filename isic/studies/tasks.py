from celery import shared_task
from django.contrib.auth.models import User

from isic.studies.models import Study
from isic.studies.services import populate_study_tasks


@shared_task(soft_time_limit=180, time_limit=300)
def populate_study_tasks_task(study_pk: int, user_pks: list[int]):
    study = Study.objects.prefetch_related('collection__images').get(pk=study_pk)
    populate_study_tasks(study=study, users=User.objects.filter(id__in=user_pks))
