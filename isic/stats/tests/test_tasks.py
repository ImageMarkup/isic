import pytest

from isic.stats.models import GaMetrics
from isic.stats.tasks import collect_google_analytics_metrics_task


@pytest.mark.django_db
def test_collect_google_analytics_task(mocker, settings):
    settings.ISIC_GOOGLE_API_JSON_KEY = 'something'

    mocker.patch('isic.stats.tasks._initialize_analyticsreporting', mocker.MagicMock)
    mocker.patch(
        'isic.stats.tasks._get_google_analytics_report',
        return_value={
            'num_sessions': 10,
            'sessions_per_country': {
                'US': 3,
                'CA': 5,
            },
        },
    )
    # only have one VIEW_ID, otherwise the counts will be multiplied
    mocker.patch('isic.stats.tasks.VIEW_IDS', ['just_one'])

    collect_google_analytics_metrics_task()

    assert GaMetrics.objects.count() == 1
    assert GaMetrics.objects.first().num_sessions == 10
    assert GaMetrics.objects.first().sessions_per_country == [
        {
            'country_name': 'United States',
            'country_numeric': '840',
            'country_alpha_2': 'US',
            'sessions': 3,
        },
        {
            'country_name': 'Canada',
            'country_numeric': '124',
            'country_alpha_2': 'CA',
            'sessions': 5,
        },
    ]
