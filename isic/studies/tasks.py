from celery import shared_task

from isic.studies.models import StudyTask


@shared_task
def create_study_task(study_id, annotator_id, image_id):
    StudyTask.objects.create(
        study_id=study_id,
        annotator_id=annotator_id,
        image_id=image_id,
    )
