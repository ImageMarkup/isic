import datetime
from datetime import timezone
from functools import lru_cache
import os

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from girder.models.user import User as GirderUser
from isic_archive.models.annotation import Annotation as GirderAnnotation
from isic_archive.models.study import Study as GirderStudy
import requests

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

    girder_user = Profile.fetch_girder_user(username)
    if not girder_user:
        return None

    try:
        user = User.objects.get(username=girder_user['email'])
    except User.DoesNotExist:
        user = User.objects.create(
            date_joined=girder_user['created'].replace(tzinfo=datetime.timezone.utc),
            username=girder_user['email'],
            email=girder_user['email'],
            password=f'bcrypt_girder${girder_user["salt"]}',
            first_name=girder_user['firstName'],
            last_name=girder_user['lastName'],
            is_active=girder_user.get('status', 'enabled') == 'enabled',
            is_staff=girder_user['admin'],
            is_superuser=girder_user['admin'],
        )
    else:
        profile_changed = user.profile.sync_from_girder()
        if profile_changed:
            user.profile.save()

    user.save()
    return user


study_gid_to_study = {}


def get_mask(file_id):
    return requests.get(
        f'https://isic-archive.com/api/v1/file/{file_id}/download',
        headers={'Girder-Token': os.environ['GIRDER_TOKEN']},
        timeout=5,
    ).content


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
                q, _ = Question.objects.get_or_create(prompt=question['id'], official=True)
                qs.append(q)
                for choice in question['choices']:
                    QuestionChoice.objects.get_or_create(question=q, text=choice)

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
                    q = Question.objects.get(prompt=question)
                    Response.objects.get_or_create(
                        annotation=sa,
                        question=q,
                        choice=QuestionChoice.objects.get(text=answer, question=q),
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
