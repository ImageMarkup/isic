# flake8: noqa
from datetime import timezone
from functools import lru_cache
import os
from typing import List, Optional

from django.core.management.base import BaseCommand
from girder.models.user import User as GirderUser
from isic_archive.models.annotation import Annotation as GirderAnnotation
from isic_archive.models.study import Study as GirderStudy
import requests

from isic.login.backends import GirderBackend
from isic.login.girder import fetch_girder_user_by_email
from isic.login.models import Profile
from isic.studies.models import (
    Annotation,
    Feature,
    Image,
    Markup,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyTask,
)


@lru_cache(maxsize=10000)
def import_user(id):
    profile = Profile.objects.filter(girder_id=str(id)).first()
    if profile:
        return profile.user

    print('importing user')
    username = GirderUser().load(id, force=True)['email']

    girder_user = fetch_girder_user_by_email(username)
    if not girder_user:
        return None

    user = GirderBackend.get_or_create_user_from_girder(girder_user)

    return user


study_gid_to_study = {}


def get_mask(file_id):
    return requests.get(
        f'https://isic-archive.com/api/v1/file/{file_id}/download',
        headers={'Girder-Token': os.environ['GIRDER_TOKEN']},
        timeout=5,
    ).content


question_mapping = {
    'Benign or Malignant': 'Does the lesion appear to be benign, malignant, or neither?',
    'Classify the Lesion as Benign or Malignant': 'Does the lesion appear to be benign or malignant?',
    'Classify the Lesion as Organized or Disorganized': 'Is the lesion organized or disorganized?',
    'Classify the lesion as benign or malignant': 'Does the lesion appear to be benign or malignant?',
    'Classify the lesion as nevus, seborrheic keratosis, or melanoma': 'Is the lesion a nevus, seborrheic keratosis, or melanoma?',
    'Colour: Black': 'Does the lesion contain the color black?',
    'Colour: Brown': 'Does the lesion contain the color brown?',
    'Colour: Grey/Blue': 'Does the lesion contain the color grey/blue?',
    'Colour: Light Brown': 'Does the lesion contain the color light brown?',
    'Colour: Red': 'Does the lesion contain the color red?',
    'Colour: White': 'Does the lesion contain the color white?',
    'Diagnosis': 'Is the lesion a nevus, melanoma, or other?',
    'Do you observe any network in the image?': 'Does the lesion contain a network?',
    'Lesion Organization': 'Is the lesion organized or disorganized?',
    "Confidence Level": 'What is your level of confidence (1-5)?',
    "Diagnosis Confidence": 'What is your level of confidence (1-5)?',
    "What is your level of confidence?": 'What is your level of confidence (1-5)?',
    'Rate your confidence level in your classification decision': 'What is your level of confidence (1-7)?',
}


def get_question(question: str, choices: Optional[List] = None) -> Question:
    prompt = question_mapping.get(question, question)
    q = Question.objects.get(prompt=prompt, official=True)
    return q


def get_choice(q: Question, choice: str) -> QuestionChoice:
    choice = (
        choice.replace('Neither Confident Nor Unconfident', 'Neither Confident / Not Confident')
        .replace('Neither Confident nor Not Confident', 'Neither Confident / Not Confident')
        .replace('Somewhat Unconfident', 'Somewhat Not Confident')
        .replace('Very Unconfident', 'Very Not Confident')
    )
    qc = QuestionChoice.objects.get(question=q, text=choice)

    return qc


class Command(BaseCommand):
    help = 'Migrate studies and annotations from Girder ISIC'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        for i, study in enumerate(GirderStudy().find()):
            print(f'on study {i}')
            qs = []
            fs = []

            # TODO: access levels

            for image in GirderStudy().getImages(study):
                Image.objects.get_or_create(object_id=image['_id'])

            print('creating questions/choices')
            for question in study['meta']['questions']:
                q = get_question(question['id'], question['choices'])
                qs.append(q)

                for choice in question['choices']:
                    get_choice(q, choice)

            print('creating features')
            for feature in study['meta']['features']:
                f, _ = Feature.objects.get_or_create(name=feature['id'].split(' : '), official=True)
                fs.append(f)

            # TODO: set feature/question/choice created to first study

            print(f'creating study {study["name"]}')
            try:
                args = {
                    'creator': import_user(str(study['creatorId'])),
                    'name': study['name'],
                    'description': study['description'],
                }
                s = Study.objects.get(**args)
                created = False
            except Study.DoesNotExist:
                created = True
                s = Study(**args)
                s.save()
                s.created = study['created'].replace(tzinfo=timezone.utc)
                s.save()

            study_gid_to_study[str(study['_id'])] = s

            print(f'setting study qs({len(qs)})/fs({len(fs)}) ')
            if created:
                s.questions.set(qs)
                s.features.set(fs)

        for i, annotation in enumerate(GirderAnnotation().find()):
            st, _ = StudyTask.objects.get_or_create(
                study=study_gid_to_study[str(annotation['studyId'])],
                annotator=import_user(str(annotation['userId'])),
                image=Image.objects.get(object_id=str(annotation['imageId'])),
            )

            if annotation['responses'] or annotation['markups']:
                sa, _ = Annotation.objects.get_or_create(
                    study=st.study, image=st.image, task=st, annotator=st.annotator
                )

                for question, answer in annotation['responses'].items():
                    q = get_question(question)
                    Response.objects.get_or_create(
                        annotation=sa, question=q, choice=get_choice(q, answer)
                    )

                if annotation['markups']:
                    for feature, meta in annotation['markups'].items():
                        mask = get_mask(str(meta['fileId']))
                        Markup.objects.get_or_create(
                            annotation=sa,
                            feature=Feature.objects.get(name=feature.split(' : ')),
                            mask=mask,
                            present=meta['present'],
                        )

            print(f'on annotation {i}')

        print('done.')
