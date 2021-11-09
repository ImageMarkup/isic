from django.contrib.auth.models import User

from isic.core.models import Collection, Image
from isic.ingest.models import Contributor, ZipUpload
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
        'uploaders_count': ZipUpload.objects.values('creator').distinct().count(),
        'annotating_users_count': Annotation.objects.values('annotator').distinct().count(),
        'total_users_count': User.objects.count(),
    }

    return ctx
