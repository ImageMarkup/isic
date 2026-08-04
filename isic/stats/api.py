from django.http.request import HttpRequest
from ninja import Router

from isic.auth import allow_any
from isic.stats.views import get_archive_stats

stats_router = Router()


@stats_router.get(
    "/",
    response=dict,
    summary="Return ISIC Archive statistics.",
    include_in_schema=False,
    auth=allow_any,
)
def stats(request: HttpRequest):
    archive_stats = get_archive_stats()

    del archive_stats["engagement"]["30_day_sessions_per_country"]
    return archive_stats
