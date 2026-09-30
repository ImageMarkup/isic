from django.urls import path
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from isic.stats.views import get_archive_stats


@api_view(["GET"])
@permission_classes([AllowAny])
def stats(request):
    archive_stats = get_archive_stats()

    del archive_stats["engagement"]["30_day_sessions_per_country"]
    return Response(archive_stats)


urlpatterns = [
    path("", stats, name="stats"),
]
