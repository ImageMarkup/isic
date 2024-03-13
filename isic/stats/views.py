from django.contrib.auth.models import User
from django.shortcuts import render

from isic.core.models import Collection, Image
from isic.ingest.models import ZipUpload
from isic.stats.models import GaMetrics
from isic.studies.models import Annotation, Study


def get_archive_stats():
    latest_ga_metrics = GaMetrics.objects.last()

    return {
        "image": {
            "images_count": Image.objects.count(),
            "public_images_count": Image.objects.public().count(),
            "annotated_images_count": Annotation.objects.values("image").distinct().count(),
        },
        "collection": {
            "collections_count": Collection.objects.count(),
            "public_collections_count": Collection.objects.public().count(),
        },
        "study": {
            "studies_count": Study.objects.count(),
            "public_studies_count": Study.objects.public().count(),
            "study_annotations_count": Annotation.objects.count(),
        },
        "user": {
            "users_count": User.objects.count(),
            "uploading_users_count": ZipUpload.objects.values("creator").distinct().count(),
            "annotating_users_count": Annotation.objects.values("annotator").distinct().count(),
        },
        "engagement": {
            "30_day_sessions_count": latest_ga_metrics.num_sessions if latest_ga_metrics else 0,
            "30_day_sessions_per_country": (
                latest_ga_metrics.sessions_per_country if latest_ga_metrics else []
            ),
        },
    }


def stats(request):
    archive_stats = get_archive_stats()
    ctx = {
        "30_day_sessions_per_country": archive_stats["engagement"]["30_day_sessions_per_country"],
        "stats": [
            [
                ("Users", archive_stats["user"]["users_count"]),
                ("Sessions (Last 30 days)", archive_stats["engagement"]["30_day_sessions_count"]),
                ("Collections", archive_stats["collection"]["collections_count"]),
            ],
            [
                ("Uploading Users", archive_stats["user"]["uploading_users_count"]),
                ("Public Collections", archive_stats["collection"]["public_collections_count"]),
                ("Annotating Users", archive_stats["user"]["annotating_users_count"]),
            ],
            [
                ("Images", archive_stats["image"]["images_count"]),
                ("Public Images", archive_stats["image"]["public_images_count"]),
                ("Annotated Images", archive_stats["image"]["annotated_images_count"]),
            ],
            [
                ("Studies", archive_stats["study"]["studies_count"]),
                ("Public Studies", archive_stats["study"]["public_studies_count"]),
                ("Annotations", archive_stats["study"]["study_annotations_count"]),
            ],
        ],
    }
    return render(request, "stats/stats.html", ctx)
