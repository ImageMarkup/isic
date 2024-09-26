import datetime
import io
import pathlib

from faker import Faker
import pytest

from isic.stats.models import GaMetrics, ImageDownload
from isic.stats.tasks import (
    _cdn_access_log_records,
    collect_google_analytics_metrics_task,
    collect_image_download_records_task,
)

fake = Faker()

data_dir = pathlib.Path(__file__).parent / "data"


@pytest.mark.django_db()
def test_collect_google_analytics_task(mocker, settings):
    # only have one VIEW_ID, otherwise the counts will be multiplied
    settings.ISIC_GOOGLE_ANALYTICS_PROPERTY_IDS = ["just_one"]
    settings.ISIC_GOOGLE_API_JSON_KEY = "something"

    mocker.patch("isic.stats.tasks._get_analytics_client", mocker.MagicMock)
    mocker.patch(
        "isic.stats.tasks._get_google_analytics_report",
        return_value={
            "num_sessions": 10,
            "sessions_per_country": {
                "US": 3,
                "CA": 5,
            },
        },
    )

    collect_google_analytics_metrics_task()

    assert GaMetrics.objects.count() == 1
    assert GaMetrics.objects.first().num_sessions == 10
    assert GaMetrics.objects.first().sessions_per_country == [
        {
            "country_name": "United States",
            "country_numeric": "840",
            "country_alpha_2": "US",
            "sessions": 3,
        },
        {
            "country_name": "Canada",
            "country_numeric": "124",
            "country_alpha_2": "CA",
            "sessions": 5,
        },
    ]


def test_cdn_access_log_parsing(mocker):
    with pathlib.Path(data_dir / "cloudfront_log.gz").open("rb") as f:
        records = list(_cdn_access_log_records(io.BytesIO(f.read())))

    assert len(records) == 24
    assert records[0] == {
        "download_time": datetime.datetime(2022, 3, 16, 3, 28, tzinfo=datetime.UTC),
        "path": "22f1e9e4-bd31-4053-9362-f8891a2b307d/17.jpg",
        "ip_address": "112.208.241.149",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36",  # noqa: E501
        "request_id": "PLFnSMEVjigrLG1hv_9OOOQUUUslSn6oo0ih_cmAbMp_tlK-ZNK1yA==",
        "status": 200,
    }


@pytest.mark.django_db()
def test_collect_image_download_records_task(
    mocker, image_factory, django_capture_on_commit_callbacks
):
    # TODO: overriding the blob name requires passing the size manually.
    image = image_factory(
        accession__blob="some/exists.jpg",
        accession__blob_name="exists.jpg",
        accession__blob_size=1,
    )

    def mock_client(*args, **kwargs):
        def _delete_object(*args, **kwargs):
            # TODO: assert that this was called?
            return {"ResponseMetadata": {"HTTPStatusCode": 204}}

        return mocker.MagicMock(delete_object=_delete_object)

    mocker.patch("isic.stats.tasks.boto3", mocker.MagicMock(client=mock_client))
    mocker.patch("isic.stats.tasks._cdn_log_objects", return_value=[{"Key": "foo"}])
    mocker.patch("isic.stats.tasks.BytesIO", mocker.MagicMock())
    mocker.patch(
        "isic.stats.tasks._cdn_access_log_records",
        return_value=[
            {
                "download_time": fake.date_time(tzinfo=fake.pytimezone()),
                "path": "some/exists.jpg",
                "ip_address": "1.1.1.1",
                "user_agent": fake.user_agent(),
                "request_id": fake.uuid4(),
                "status": 200,
            },
            {
                "download_time": fake.date_time(tzinfo=fake.pytimezone()),
                "path": "some/doesnt-exist.jpg",
                "ip_address": "1.1.1.1",
                "user_agent": fake.user_agent(),
                "request_id": fake.uuid4(),
                "status": 200,
            },
            {
                "download_time": fake.date_time(tzinfo=fake.pytimezone()),
                "path": "some/a-cog.tif?Expires=12345&Signature=...",
                "ip_address": "1.1.1.1",
                "user_agent": fake.user_agent(),
                "request_id": fake.uuid4(),
                "status": 206,
            },
            {
                "download_time": fake.date_time(tzinfo=fake.pytimezone()),
                "path": "some/exists-2.jpg",
                "ip_address": "1.1.1.1",
                "user_agent": fake.user_agent(),
                "request_id": fake.uuid4(),
                "status": 403,
            },
            {
                "download_time": fake.date_time(tzinfo=fake.pytimezone()),
                "path": "some/doesnt-exist-2.jpg",
                "ip_address": "1.1.1.1",
                "user_agent": fake.user_agent(),
                "request_id": fake.uuid4(),
                "status": 403,
            },
        ],
    )

    with django_capture_on_commit_callbacks(execute=True):
        collect_image_download_records_task()

    assert ImageDownload.objects.count() == 1
    assert image.downloads.count() == 1
