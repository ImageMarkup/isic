from celery import shared_task

from isic.studies.models import StudyTask


@shared_task
def create_study_task(study_pk, annotator_pk, image_pk):
    # For efficiency, set the _id fields directly, instead of loading ForeignKey references
    StudyTask.objects.create(
        study_id=study_pk,
        annotator_id=annotator_pk,
        image_id=image_pk,
    )
