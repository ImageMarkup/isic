from faker import Faker
import pytest

from isic.stats.models import GaMetrics, ImageDownload
from isic.stats.tasks import (
    collect_google_analytics_metrics_task,
    collect_image_download_records_task,
)

fake = Faker()


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


@pytest.mark.django_db
def test_collect_image_download_records_task(mocker, image_factory):
    image = image_factory(accession__blob='some/exists.jpg')

    def mock_client(*args, **kwargs):
        return mocker.MagicMock(delete_objects=lambda **_: {})

    mocker.patch('isic.stats.tasks.boto3', mocker.MagicMock(client=mock_client))
    mocker.patch('isic.stats.tasks._cdn_log_objects', return_value=[{'Key': 'foo'}])
    mocker.patch(
        'isic.stats.tasks._cdn_access_log_records',
        return_value=[
            {
                'download_time': fake.date_time(tzinfo=fake.pytimezone()),
                'path': 'some/exists.jpg',
                'ip_address': '1.1.1.1',
                'request_id': fake.uuid4(),
                'status': 200,
            },
            {
                'download_time': fake.date_time(tzinfo=fake.pytimezone()),
                'path': 'some/doesnt-exist.jpg',
                'ip_address': '1.1.1.1',
                'request_id': fake.uuid4(),
                'status': 200,
            },
            {
                'download_time': fake.date_time(tzinfo=fake.pytimezone()),
                'path': 'some/exists-2.jpg',
                'ip_address': '1.1.1.1',
                'request_id': fake.uuid4(),
                'status': 403,
            },
            {
                'download_time': fake.date_time(tzinfo=fake.pytimezone()),
                'path': 'some/doesnt-exist-2.jpg',
                'ip_address': '1.1.1.1',
                'request_id': fake.uuid4(),
                'status': 403,
            },
        ],
    )

    collect_image_download_records_task()

    assert ImageDownload.objects.count() == 1
    assert image.downloads.count() == 1

    # TODO: assert file is deleted with boto, this is tricky to do with mocking
