import datetime

from django.db import transaction
import djclick as click

from isic.studies.models import Response, Study

STUDY_ID = 92
STUDY_CREATED = datetime.datetime(2018, 8, 4)
STUDY_RESPONDED = datetime.datetime(2018, 9, 30)


@click.command()
def forge_reader_study_dates():
    with transaction.atomic():
        study = Study.objects.get(pk=STUDY_ID)

        # set initialization dates
        Study.objects.filter(pk=STUDY_ID).update(created=STUDY_CREATED, modified=STUDY_CREATED)
        study.questions.update(created=STUDY_CREATED, modified=STUDY_CREATED)
        study.tasks.update(created=STUDY_CREATED, modified=STUDY_CREATED)

        # set response dates
        study.annotations.update(created=STUDY_RESPONDED, modified=STUDY_RESPONDED)
        Response.objects.filter(annotation__study__pk=STUDY_ID).update(
            created=STUDY_RESPONDED, modified=STUDY_RESPONDED
        )
