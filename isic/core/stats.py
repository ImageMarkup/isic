from django.conf import settings

from isic.core.models import Collection, Image
from isic.ingest.models import Contributor, Zip
from isic.login.girder import get_girder_db
from isic.studies.models import Annotation, Markup, Response, Study


def get_archive_stats():
    ctx = {
        'annotations_count': Annotation.objects.count(),
        'collections_count': Collection.objects.count(),
        'contributors_count': Contributor.objects.count(),
        'images_count': Image.objects.count(),
        'markups_count': Markup.objects.count(),
        'public_images_count': Image.objects.filter(public=True).count(),
        'public_studies_count': Study.objects.filter(public=True).count(),
        'responses_count': Response.objects.count(),
        'studies_count': Study.objects.count(),
        'annotated_images_count': Annotation.objects.values('image').distinct().count(),
        'uploaders_count': Zip.objects.values('creator').distinct().count(),
        'annotating_users_count': Annotation.objects.values('annotator').distinct().count(),
    }

    if settings.ISIC_MONGO_URI:
        ctx['total_users_count'] = get_girder_db()['user'].count()
    else:
        ctx['total_users_count'] = 0

    return ctx
