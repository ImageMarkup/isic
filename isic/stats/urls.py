from django.urls import path

from isic.stats.views import stats

urlpatterns = [
    path(
        'stats/',
        stats,
        name='stats/stats',
    ),
]
