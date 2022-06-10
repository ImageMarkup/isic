import sys

from django.contrib.auth.models import User
from django.db import transaction
import djclick as click
import pandas as pd

from isic.core.models.collection import Collection
from isic.studies.models import Annotation, Question, Response, Study
from isic.studies.services import populate_study_tasks


@click.command()
@click.argument('study_name')
@click.argument('study_creator_id')
@click.argument('collection_id')
@click.argument('column_question_mapping_csv')
@click.argument('responses_csv')
@transaction.atomic()
def create_study_from_csv(
    study_name, study_creator_id, collection_id, column_question_mapping_csv, responses_csv
):
    column_question_df = pd.read_csv(column_question_mapping_csv, header=0)

    if 'column_name' not in column_question_df.columns:
        click.secho('Unable to find column "column_name".', err=True, fg='red')
        sys.exit(1)
    elif 'question_id' not in column_question_df.columns:
        click.secho('Unable to find column "question_id".', err=True, fg='red')
        sys.exit(1)

    column_question = column_question_df.set_index('column_name').to_dict()['question_id']

    responses_df = pd.read_csv(responses_csv, header=0)

    if 'isic_id' not in responses_df.columns:
        click.secho('Unable to find column "isic_id".', err=True, fg='red')
        sys.exit(1)
    elif 'annotator_id' not in responses_df.columns:
        click.secho('Unable to find column "annotator_id".', err=True, fg='red')
        sys.exit(1)

    study_creator = User.objects.filter(id=study_creator_id).first()

    if not study_creator:
        click.secho(f'Unable to find user with id {study_creator_id}.', err=True, fg='red')
        sys.exit(1)

    collection = Collection.objects.filter(id=collection_id).first()

    if not collection:
        click.secho(f'Unable to find collection with id {collection_id}.', err=True, fg='red')
        sys.exit(1)

    study, _ = Study.objects.get_or_create(
        creator=study_creator,
        name=study_name,
        description='-',
        collection=collection,
        public=False,
    )

    collection.locked = True
    collection.save(update_fields=['locked'])

    for question_id in column_question.values():
        study.questions.add(
            Question.objects.get(id=question_id), through_defaults={'required': True}
        )

    click.secho('Populating study tasks', err=True, fg='yellow')
    populate_study_tasks(
        study=study, users=User.objects.filter(id__in=responses_df['annotator_id'])
    )

    annotations = []
    responses = []
    with click.progressbar(
        responses_df.iterrows(), length=len(responses_df), label='Creating responses'
    ) as bar:
        for _, row in bar:
            task = study.tasks.get(annotator__pk=row['annotator_id'], image__isic_id=row['isic_id'])
            annotation = Annotation(
                study_id=task.study_id,
                image_id=task.image_id,
                task=task,
                annotator_id=row['annotator_id'],
            )
            annotations.append(annotation)

            for key, value in row.items():

                if key not in ['isic_id', 'annotator_id']:
                    if key not in column_question.keys():
                        click.secho(
                            f'Skipping column {key} not found in mapping csv.',
                            err=True,
                            fg='yellow',
                        )
                    elif pd.isna(value):
                        click.secho(
                            f'Skipping response because {key} is null or NaN.',
                            err=True,
                            fg='yellow',
                        )
                    else:
                        response = Response(
                            annotation=annotation,
                            question_id=column_question[key],
                            value=value,
                        )
                        responses.append(response)

    Annotation.objects.bulk_create(annotations, batch_size=1_000)
    Response.objects.bulk_create(responses, batch_size=1_000)
