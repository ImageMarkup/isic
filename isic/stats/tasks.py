from collections import defaultdict
from datetime import timedelta
import json
from types import SimpleNamespace

from apiclient.discovery import build
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone
from oauth2client.service_account import ServiceAccountCredentials
import pycountry

from isic.stats.models import GaMetrics

SCOPES = ['https://www.googleapis.com/auth/analytics.readonly']
VIEW_IDS = [
    '110224626',  # ISIC Archive Admin
    '183845203',  # ISIC Archive Frontend
    '172830666',  # ISIC Challenge 2018
    '195202197',  # ISIC Challenge 2019
    '217814783',  # ISIC Challenge 2020
    '199577101',  # ISIC Challenge Submission
]


logger = get_task_logger(__name__)


def _initialize_analyticsreporting():
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(settings.ISIC_GOOGLE_API_JSON_KEY), SCOPES
    )
    analytics = build('analyticsreporting', 'v4', credentials=credentials)
    return analytics


def _get_google_analytics_report(analytics, view_id: str) -> dict:
    results = {
        'num_sessions': 0,
        'sessions_per_country': defaultdict(int),
    }
    response = (
        analytics.reports()
        .batchGet(
            body={
                'reportRequests': [
                    {
                        'viewId': view_id,
                        'dateRanges': [{'startDate': '30daysAgo', 'endDate': 'today'}],
                        'metrics': [{'expression': 'ga:sessions'}],
                        'dimensions': [{'name': 'ga:countryIsoCode'}],
                    }
                ]
            }
        )
        .execute()
    )

    for report in response.get('reports', []):
        column_header = report.get('columnHeader', {})
        metric_headers = column_header.get('metricHeader', {}).get('metricHeaderEntries', [])

        for row in report.get('data', {}).get('rows', []):
            dimensions = row.get('dimensions', [])
            date_range_values = row.get('metrics', [])

            for _, values in enumerate(date_range_values):
                for _, value in zip(metric_headers, values.get('values')):
                    if dimensions[0] != 'ZZ':  # unknown country
                        results['sessions_per_country'][dimensions[0]] += int(value)

        results['num_sessions'] += int(
            report.get('data', {}).get('totals', [{}])[0].get('values', ['0'])[0]
        )

    return results


def _country_from_iso_code(iso_code: str) -> dict:
    country = pycountry.countries.get(alpha_2=iso_code)

    # https://github.com/flyingcircusio/pycountry/issues/70
    if iso_code == 'XK':
        country = SimpleNamespace(alpha_2='XK', numeric='383', name='Kosovo')

    if not country:
        logger.error(f'Unable to find country {iso_code}.')

    return {
        'country_alpha_2': country.alpha_2,
        'country_numeric': country.numeric,
        'country_name': country.name,
    }


@shared_task(soft_time_limit=20, time_limit=60)
def collect_google_analytics_metrics_task():
    if not settings.ISIC_GOOGLE_API_JSON_KEY:
        logger.info(
            'Skipping google analytics collection, ISIC_GOOGLE_API_JSON_KEY not configured.'
        )
        return

    analytics = _initialize_analyticsreporting()
    num_sessions = 0
    sessions_per_country = []
    sessions_per_iso_code: dict[str, int] = defaultdict(int)

    for view_id in VIEW_IDS:
        results = _get_google_analytics_report(analytics, view_id)
        num_sessions += results['num_sessions']
        for key, value in results['sessions_per_country'].items():
            sessions_per_iso_code[key] += value

    for iso_code, sessions in sessions_per_iso_code.items():
        sessions_per_country.append({**{'sessions': sessions}, **_country_from_iso_code(iso_code)})

    GaMetrics.objects.create(
        range_start=timezone.now() - timedelta(days=30),
        range_end=timezone.now(),
        num_sessions=num_sessions,
        sessions_per_country=sessions_per_country,
    )
