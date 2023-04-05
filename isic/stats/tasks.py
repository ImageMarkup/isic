from collections import defaultdict
from datetime import timedelta
import gzip
from io import BytesIO
import json
from types import SimpleNamespace
from typing import Iterable
import urllib.parse

from apiclient.discovery import build
import boto3
from botocore.config import Config
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from googleapiclient.errors import HttpError
from more_itertools.more import chunked
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import pycountry

from isic.core.models.image import Image
from isic.stats.models import GaMetrics, ImageDownload

SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]


logger = get_task_logger(__name__)


def _s3_client():
    return boto3.client(
        "s3", config=Config(connect_timeout=3, read_timeout=10, retries={"max_attempts": 5})
    )


def _initialize_analyticsreporting():
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(settings.ISIC_GOOGLE_API_JSON_KEY), SCOPES
    )
    analytics = build("analyticsreporting", "v4", credentials=credentials)
    return analytics


def _get_google_analytics_report(analytics, view_id: str) -> dict:
    results = {
        "num_sessions": 0,
        "sessions_per_country": defaultdict(int),
    }
    response = (
        analytics.reports()
        .batchGet(
            body={
                "reportRequests": [
                    {
                        "viewId": view_id,
                        "dateRanges": [{"startDate": "30daysAgo", "endDate": "today"}],
                        "metrics": [{"expression": "ga:sessions"}],
                        "dimensions": [{"name": "ga:countryIsoCode"}],
                    }
                ]
            }
        )
        .execute()
    )

    for report in response.get("reports", []):
        column_header = report.get("columnHeader", {})
        metric_headers = column_header.get("metricHeader", {}).get("metricHeaderEntries", [])

        for row in report.get("data", {}).get("rows", []):
            dimensions = row.get("dimensions", [])
            date_range_values = row.get("metrics", [])

            for _, values in enumerate(date_range_values):
                for _, value in zip(metric_headers, values.get("values")):
                    if dimensions[0] != "ZZ":  # unknown country
                        results["sessions_per_country"][dimensions[0]] += int(value)

        results["num_sessions"] += int(
            report.get("data", {}).get("totals", [{}])[0].get("values", ["0"])[0]
        )

    return results


def _country_from_iso_code(iso_code: str) -> dict:
    country = pycountry.countries.get(alpha_2=iso_code)

    # https://github.com/flyingcircusio/pycountry/issues/70
    if iso_code == "XK":
        country = SimpleNamespace(alpha_2="XK", numeric="383", name="Kosovo")

    if not country:
        raise Exception(f"Unable to find country {iso_code}.")

    return {
        "country_alpha_2": country.alpha_2,
        "country_numeric": country.numeric,
        "country_name": country.name,
    }


@shared_task(
    soft_time_limit=60,
    time_limit=120,
    # Figuring out retries within googleapiclient is a bit cumbersome, use celery.
    autoretry_for=(HttpError,),
    retry_backoff=True,
)
def collect_google_analytics_metrics_task():
    if not settings.ISIC_GOOGLE_API_JSON_KEY:
        logger.info(
            "Skipping google analytics collection, ISIC_GOOGLE_API_JSON_KEY not configured."
        )
        return

    analytics = _initialize_analyticsreporting()
    num_sessions = 0
    sessions_per_country = []
    sessions_per_iso_code: dict[str, int] = defaultdict(int)

    for view_id in settings.ISIC_GOOGLE_ANALYTICS_VIEW_IDS:
        results = _get_google_analytics_report(analytics, view_id)
        num_sessions += results["num_sessions"]
        for key, value in results["sessions_per_country"].items():
            sessions_per_iso_code[key] += value

    for iso_code, sessions in sessions_per_iso_code.items():
        sessions_per_country.append({**{"sessions": sessions}, **_country_from_iso_code(iso_code)})

    GaMetrics.objects.create(
        range_start=timezone.now() - timedelta(days=30),
        range_end=timezone.now(),
        num_sessions=num_sessions,
        sessions_per_country=sessions_per_country,
    )


def _cdn_log_objects(s3) -> Iterable[dict]:
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=settings.CDN_LOG_BUCKET)
    for page in pages:
        yield from page.get("Contents", [])


def _cdn_access_log_records(s3, s3_log_object_key: str) -> Iterable[dict]:
    data = s3.get_object(Bucket=settings.CDN_LOG_BUCKET, Key=s3_log_object_key)

    with gzip.GzipFile(fileobj=BytesIO(data["Body"].read())) as stream:
        version_line, headers_line = stream.readlines()[0:2]
        assert version_line.decode("utf-8").strip() == "#Version: 1.0"
        headers = headers_line.decode("utf-8").replace("#Fields:", "").strip().split()
        stream.seek(0)
        df = pd.read_table(
            stream,
            skiprows=2,
            names=headers,
            usecols=[
                "date",
                "time",
                "cs-uri-stem",
                "c-ip",
                "cs(User-Agent)",
                "x-edge-request-id",
                "sc-status",
            ],
            delimiter="\\s+",
        )

    df["download_time"] = pd.to_datetime(df["date"] + " " + df["time"], utc=True)

    for _, row in df.iterrows():
        yield {
            "download_time": row["download_time"],
            "path": row["cs-uri-stem"].lstrip("/"),
            "ip_address": row["c-ip"],
            "user_agent": urllib.parse.unquote(row["cs(User-Agent)"]),
            "request_id": row["x-edge-request-id"],
            "status": row["sc-status"],
        }


@shared_task(soft_time_limit=60, time_limit=120)
def collect_image_download_records_task():
    s3 = _s3_client()

    # gather all request log entries and group them by path
    for s3_log_object in _cdn_log_objects(s3):
        # break this out into subtasks as a single log file can consume a large amount of ram.
        process_s3_log_file_task.delay(s3_log_object["Key"])


@shared_task(soft_time_limit=600, time_limit=610)
def process_s3_log_file_task(s3_log_object_key: str):
    s3 = _s3_client()

    with transaction.atomic():
        # go through only the images that mapped onto request paths (this ignores thumbnails and
        # other files). this can create a query with tens of thousands of elements in the "where in"
        # clause, so it needs to be batched.
        for download_logs in chunked(
            filter(lambda r: r["status"] == 200, _cdn_access_log_records(s3, s3_log_object_key)),
            1_000,
        ):
            # if any request_id has already been processed, it means the entire file has been.
            # this means the task is being executed again, and should avoid processing log files
            # but needs to delete the log file from s3.
            if ImageDownload.objects.filter(request_id=download_logs[0]["request_id"]).exists():
                logger.info("Skipping already processed log file %s", s3_log_object_key)
                break

            downloaded_paths_to_image_id: dict[str, int] = dict(
                Image.objects.filter(
                    accession__blob__in=[download_log["path"] for download_log in download_logs]
                ).values_list("accession__blob", "id")
            )

            image_downloads: list[ImageDownload] = []

            for download_log in download_logs:
                if download_log["path"] in downloaded_paths_to_image_id:
                    image_downloads.append(
                        ImageDownload(
                            download_time=download_log["download_time"],
                            ip_address=download_log["ip_address"],
                            user_agent=download_log["user_agent"],
                            request_id=download_log["request_id"],
                            image_id=downloaded_paths_to_image_id[download_log["path"]],
                        )
                    )

            ImageDownload.objects.bulk_create(image_downloads)

    delete = s3.delete_object(
        Bucket=settings.CDN_LOG_BUCKET,
        Key=s3_log_object_key,
    )
    assert delete["ResponseMetadata"]["HTTPStatusCode"] == 204
