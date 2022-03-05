from collections import defaultdict
from datetime import timedelta
import gzip
from io import BytesIO
import json
from types import SimpleNamespace
from typing import Iterable

from apiclient.discovery import build
import boto3
from botocore.config import Config
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import pycountry

from isic.core.models.image import Image
from isic.stats.models import GaMetrics, ImageDownload

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
        raise Exception(f'Unable to find country {iso_code}.')

    return {
        'country_alpha_2': country.alpha_2,
        'country_numeric': country.numeric,
        'country_name': country.name,
    }


@shared_task(
    soft_time_limit=20,
    time_limit=60,
    # Figuring out retries within googleapiclient is a bit cumbersome, use celery.
    autoretry_for=(HttpError,),
    retry_backoff=True,
)
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


def _cdn_log_objects(s3) -> Iterable[dict]:
    pages = s3.get_paginator('list_objects_v2').paginate(Bucket=settings.CDN_LOG_BUCKET)
    for page in pages:
        yield from page.get('Contents', [])


def _cdn_access_log_successful_requests(log_file_bytes) -> Iterable[dict]:
    with gzip.GzipFile(fileobj=BytesIO(log_file_bytes)) as stream:
        version_line, headers_line = stream.readlines()[0:2]
        assert version_line.decode('utf-8').strip() == '#Version: 1.0'
        headers = headers_line.decode('utf-8').replace('#Fields:', '').strip().split()
        stream.seek(0)
        df = pd.read_table(stream, skiprows=2, names=headers, delimiter='\\s+')

    df['download_time'] = pd.to_datetime(df['date'] + ' ' + df['time'], utc=True)
    successful_downloads_df = df[df['sc-status'] == 200]

    for _, row in successful_downloads_df.iterrows():
        yield {
            'download_time': row['download_time'],
            'path': row['cs-uri-stem'],
            'ip_address': row['c-ip'],
            'request_id': row['x-edge-request-id'],
        }


# note the time limit is dependent on how frequently this is run.
@shared_task(soft_time_limit=300, time_limit=360)
@transaction.atomic()
def collect_image_download_records():
    s3 = boto3.client(
        's3', config=Config(connect_timeout=3, read_timeout=10, retries={'max_attempts': 5})
    )
    image_downloads: list[ImageDownload] = []
    processed_s3_keys: list[str] = []

    for s3_object in _cdn_log_objects(s3):
        data = s3.get_object(Bucket=settings.CDN_LOG_BUCKET, Key=s3_object['Key'])
        for request in _cdn_access_log_successful_requests(data['Body'].read()):
            # TODO: maybe optimize in the future to do one IN query
            downloaded_image = Image.objects.filter(
                accession__blob=request['path'].lstrip('/')
            ).first()
            if downloaded_image:
                image_downloads.append(
                    ImageDownload(
                        download_time=request['download_time'],
                        ip_address=request['ip_address'],
                        request_id=request['request_id'],
                        image=downloaded_image,
                    )
                )

        processed_s3_keys.append(s3_object['Key'])

    ImageDownload.objects.bulk_create(image_downloads)

    if processed_s3_keys:
        delete_response = s3.delete_objects(
            Bucket=settings.CDN_LOG_BUCKET,
            Delete={'Objects': [{'Key': key} for key in processed_s3_keys]},
        )
        assert not delete_response.get('Errors')
