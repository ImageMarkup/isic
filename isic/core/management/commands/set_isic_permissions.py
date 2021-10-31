from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
import djclick as click

from isic.core.models import Collection, DuplicateImage, Image, ImageAlias
from isic.ingest.models import (
    Accession,
    CheckLog,
    Cohort,
    Contributor,
    DistinctnessMeasure,
    MetadataFile,
    ZipUpload,
)
from isic.studies.models import (
    Annotation,
    Feature,
    Markup,
    Question,
    QuestionChoice,
    Response,
    Study,
    StudyTask,
)


@click.command(help='Add ISIC Staff group with basic permissions')
def add_staff_group():
    group, _ = Group.objects.get_or_create(name='ISIC Staff')

    for model in [
        Accession,
        Annotation,
        CheckLog,
        Cohort,
        Collection,
        Contributor,
        DistinctnessMeasure,
        DuplicateImage,
        Feature,
        Image,
        ImageAlias,
        Markup,
        MetadataFile,
        Question,
        QuestionChoice,
        Response,
        Study,
        StudyTask,
        User,
        ZipUpload,
    ]:
        content_type = ContentType.objects.get_for_model(model)
        for permission in ['view', 'change']:
            group.permissions.add(
                Permission.objects.get(
                    codename=f'{permission}_{content_type.model}',
                    content_type=content_type,
                )
            )
