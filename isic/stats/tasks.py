from collections import defaultdict
from collections.abc import Iterable
from datetime import timedelta
import gzip
from io import BytesIO
import itertools
import json
from types import SimpleNamespace
import urllib.parse

import boto3
from botocore.config import Config
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.db import transaction
from django.db.utils import IntegrityError
from django.utils import timezone
import pycountry

from isic.core.models.image import Image
from isic.stats.models import GaMetrics, ImageDownload

logger = get_task_logger(__name__)


def _s3_client():
    return boto3.client(
        "s3", config=Config(connect_timeout=3, read_timeout=10, retries={"max_attempts": 5})
    )


def _get_analytics_client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.oauth2 import service_account

    json_acct_info = json.loads(settings.ISIC_GOOGLE_API_JSON_KEY)
    credentials = service_account.Credentials.from_service_account_info(json_acct_info)
    scoped_credentials = credentials.with_scopes(
        ["https://www.googleapis.com/auth/analytics.readonly"]
    )
    return BetaAnalyticsDataClient(credentials=scoped_credentials)


def _get_google_analytics_report(client, property_id: str) -> dict:
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

    results = {
        "num_sessions": 0,
        "sessions_per_country": defaultdict(int),
    }

    request = RunReportRequest(
        property=f"properties/{property_id}",
        dimensions=[Dimension(name="countryId")],
        metrics=[Metric(name="sessions")],
        date_ranges=[DateRange(start_date="30daysAgo", end_date="today")],
    )
    response = client.run_report(request)

    for row in response.rows:
        country_id, sessions = row.dimension_values[0].value, row.metric_values[0].value
        results["sessions_per_country"][country_id] += int(sessions)
        results["num_sessions"] += int(sessions)

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
)
def collect_google_analytics_metrics_task():
    if not settings.ISIC_GOOGLE_API_JSON_KEY:
        logger.info(
            "Skipping google analytics collection, ISIC_GOOGLE_API_JSON_KEY not configured."
        )
        return

    client = _get_analytics_client()
    num_sessions = 0
    sessions_per_country = []
    sessions_per_iso_code: dict[str, int] = defaultdict(int)

    for property_id in settings.ISIC_GOOGLE_ANALYTICS_PROPERTY_IDS:
        results = _get_google_analytics_report(client, property_id)
        num_sessions += results["num_sessions"]
        for key, value in results["sessions_per_country"].items():
            sessions_per_iso_code[key] += value

    for iso_code, sessions in sessions_per_iso_code.items():
        if iso_code not in ["(not set)", ""]:
            sessions_per_country.append({"sessions": sessions, **_country_from_iso_code(iso_code)})

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


def _cdn_access_log_records(log_file_bytes: BytesIO) -> Iterable[dict]:
    import pandas as pd

    with gzip.GzipFile(fileobj=log_file_bytes) as stream:
        version_line, headers_line = stream.readlines()[0:2]
        if not version_line.startswith(b"#Version: 1.0"):
            raise Exception("Unknown version in log file")

        headers = headers_line.decode("utf-8").replace("#Fields:", "").strip().split()
        stream.seek(0)
        logs = pd.read_table(
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

    logs["download_time"] = pd.to_datetime(logs["date"] + " " + logs["time"], utc=True)

    for _, row in logs.iterrows():
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
        process_s3_log_file_task.delay_on_commit(s3_log_object["Key"])


@shared_task(soft_time_limit=600, time_limit=630, max_retries=5, retry_backoff=True)
def process_s3_log_file_task(s3_log_object_key: str):
    s3 = _s3_client()

    try:
        data = s3.get_object(Bucket=settings.CDN_LOG_BUCKET, Key=s3_log_object_key)
    except s3.exceptions.NoSuchKey:
        # ignore the case where it was already processed and deleted by another task
        return

    log_file_bytes = BytesIO(data["Body"].read())

    _process_s3_log_file_task(log_file_bytes)

    delete = s3.delete_object(
        Bucket=settings.CDN_LOG_BUCKET,
        Key=s3_log_object_key,
    )

    if delete["ResponseMetadata"]["HTTPStatusCode"] != 204:
        raise Exception(f"Failed to delete s3 log file {s3_log_object_key}")


def _process_s3_log_file_task(log_file_bytes: BytesIO):
    # This batch size is important because it bounds the size of the bulk creations
    # AND (implicitly) the number of items in the "where in" clause.
    BATCH_SIZE = 1_000  # noqa: N806

    with transaction.atomic():
        # go through only the images that mapped onto request paths (this ignores thumbnails and
        # other files). this can create a query with tens of thousands of elements in the "where in"
        # clause, so it needs to be batched.
        # note that the COG images return a 206 partial content status, so this doesn't count
        # the individual tiles that are downloaded.
        for download_logs in itertools.batched(
            filter(lambda r: r["status"] == 200, _cdn_access_log_records(log_file_bytes)),
            BATCH_SIZE,
        ):
            # if any request_id has already been processed, it means the entire file has been.
            # this means the task is being executed again, and should avoid processing log files
            # but needs to delete the log file from s3.
            if ImageDownload.objects.filter(request_id=download_logs[0]["request_id"]).exists():
                logger.info("Skipping already processed log file")
                break

            downloaded_paths_to_image_id: dict[str, int] = dict(
                Image.objects.filter(
                    accession__blob__in=[download_log["path"] for download_log in download_logs]
                ).values_list("accession__blob", "id")
            )

            image_downloads: list[ImageDownload] = []

            for download_log in download_logs:
                if download_log["path"] in downloaded_paths_to_image_id:
                    image_downloads.append(  # noqa: PERF401
                        ImageDownload(
                            download_time=download_log["download_time"],
                            ip_address=download_log["ip_address"],
                            user_agent=download_log["user_agent"],
                            request_id=download_log["request_id"],
                            image_id=downloaded_paths_to_image_id[download_log["path"]],
                        )
                    )

            try:
                ImageDownload.objects.bulk_create(image_downloads, batch_size=BATCH_SIZE)
            except IntegrityError as e:
                # Ignore duplicate entries, this is necessary because another transaction can be
                # committed between the time of the earlier check and now.
                # See https://www.postgresql.org/docs/current/errcodes-appendix.html
                if e.__cause__.pgcode != "23505":
                    raise
