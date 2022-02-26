from django.urls import path

from isic.stats.api import stats as api_stats
from isic.stats.views import stats

urlpatterns = [
    path(
        'stats/',
        stats,
        name='stats/stats',
    ),
    path('api/v2/stats/', api_stats, name='stats/api/stats'),
]
