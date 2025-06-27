from datetime import UTC, datetime

from django.conf import settings
from django.db.models import Count
import djclick as click
import duckdb
from google.analytics.data_v1beta.types import DateRange, Metric, RunReportRequest

from isic.core.models.doi import Doi
from isic.ingest.models import Accession
from isic.ingest.models.accession_review import AccessionReview
from isic.stats.tasks import _get_analytics_client


def _get_google_analytics_sessions(start_date: str, end_date: str) -> int:
    client = _get_analytics_client()
    total = 0
    for property_id in settings.ISIC_GOOGLE_ANALYTICS_PROPERTY_IDS:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        )
        response = client.run_report(request)
        total += sum(int(row.metric_values[0].value) for row in response.rows)
    return total


@click.command(help="Print ISIC Archive statistics for a given date range")
@click.argument("duckdb_path", type=str)
@click.argument("start_date", type=str)
@click.argument("end_date", type=str)
def archive_statistics(duckdb_path: str, start_date: str, end_date: str):
    """
    Print ISIC Archive statistics for a given date range.

    DUCKDB_PATH is a path to a duckdb database with a table named logs. The table needs to have
    a download_time (bigint), request_id (text), user_agent (text), and image_id (bigint) column.
    The database can be built by selecting a subset of the stats_imagedownload table, possibly
    joined with parquet files from certain time ranges. The request_id is used to deduplicate rows.

    START_DATE and END_DATE are strings in the format YYYY-MM-DD.
    """
    con = duckdb.connect(duckdb_path)

    # produce consumption numbers
    ga_sessions = _get_google_analytics_sessions(start_date, end_date)
    click.echo(f"Google Analytics sessions: {ga_sessions:,}")

    query = f"""
        select case when user_agent like 'isic-cli/%' then 'isic-cli'
                when user_agent like 'isic-zipstreamer/%' or user_agent like 'Go-http-client%' then 'zip'
                else 'api/gallery' end as user_agent,
           count(*)
    from logs
    where download_time > epoch('{start_date}'::timestamp) and download_time < epoch('{end_date}'::timestamp)
    group by 1
    order by 1"""  # noqa: E501, S608

    click.echo("\nDownloads by access method:")
    for user_agent, count in con.sql(query).fetchall():
        click.echo(f"{user_agent:20s}: {count:,}")

    click.echo("\nTotal downloads:")
    total_downloads = con.sql(
        f"select count(*) from logs where download_time < epoch('{end_date}'::timestamp)"  # noqa: S608
    ).fetchone()
    assert total_downloads is not None  # noqa: S101
    click.echo(f"{total_downloads[0]:,}")

    # add utc offset to start and end dates
    start_date_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=UTC)
    end_date_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=UTC)

    # contribution numbers
    accessions = Accession.objects.filter(created__gte=start_date_dt, created__lte=end_date_dt)
    click.echo(f"\nAccessions created: {accessions.count():,}")

    user_review_counts = dict(
        AccessionReview.objects.filter(reviewed_at__gte=start_date_dt, reviewed_at__lte=end_date_dt)
        .values("creator")
        .annotate(count=Count("id"))
        .values_list("creator__username", "count")
    )
    click.echo("\nReview counts by reviewer:")
    for reviewer, count in user_review_counts.items():
        click.echo(f"{reviewer}: {count:,}")

    dois_created = Doi.objects.filter(created__gte=start_date_dt, created__lte=end_date_dt)
    click.echo("\nDOIs created:")
    for doi in dois_created:
        click.echo(f"{doi.id} ({doi.collection.name})")

    total_accession_count = Accession.objects.filter(created__lte=end_date_dt).count()
    click.echo(f"\nTotal accession count: {total_accession_count:,}")
