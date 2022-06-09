from django.contrib.auth.models import User
from django.shortcuts import render

from isic.core.models import Collection, Image
from isic.ingest.models import Contributor, ZipUpload
from isic.stats.models import GaMetrics
from isic.studies.models import Annotation, Markup, Response, Study


def get_archive_stats():
    latest_ga_metrics = GaMetrics.objects.last()

    ctx = {
        'annotations_count': Annotation.objects.count(),
        'collections_count': Collection.objects.count(),
        'contributors_count': Contributor.objects.count(),
        'images_count': Image.objects.count(),
        'markups_count': Markup.objects.count(),
        'public_images_count': Image.objects.public().count(),
        'public_studies_count': Study.objects.public().count(),
        'responses_count': Response.objects.count(),
        'studies_count': Study.objects.count(),
        'annotated_images_count': Annotation.objects.values('image').distinct().count(),
        # TODO: keep?
        'uploaders_count': ZipUpload.objects.values('creator').distinct().count(),
        'annotating_users_count': Annotation.objects.values('annotator').distinct().count(),
        'total_users_count': User.objects.count(),
    }

    if latest_ga_metrics:
        ctx['sessions_last_30_days_count'] = latest_ga_metrics.num_sessions
        ctx['sessions_last_30_days_per_country'] = latest_ga_metrics.sessions_per_country
    else:
        ctx['sessions_last_30_days_count'] = 0
        ctx['sessions_last_30_days_per_country'] = []

    return ctx


def stats(request):
    archive_stats = get_archive_stats()
    ctx = {
        'sessions_last_30_days_per_country': archive_stats['sessions_last_30_days_per_country'],
        'stats': [
            [
                ('Users', archive_stats['total_users_count']),
                ('Sessions (Last 30 days)', archive_stats['sessions_last_30_days_count']),
                ('Annotating Users', archive_stats['annotating_users_count']),
            ],
            [
                ('Contributing Institutions', archive_stats['contributors_count']),
                ('', ''),
                ('Collections', archive_stats['collections_count']),
            ],
            [
                ('Images', archive_stats['images_count']),
                ('Public Images', archive_stats['public_images_count']),
                ('Annotated Images', archive_stats['annotated_images_count']),
            ],
            [
                ('Studies', archive_stats['studies_count']),
                ('Public Studies', archive_stats['public_studies_count']),
                ('', ''),
            ],
            [
                ('Annotations', archive_stats['annotations_count']),
                ('Markups', archive_stats['markups_count']),
                ('Responses', archive_stats['responses_count']),
            ],
        ],
    }
    return render(request, 'stats/stats.html', ctx)
