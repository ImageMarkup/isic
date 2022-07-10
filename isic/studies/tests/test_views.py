from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_study_responses_csv(staff_client, private_study_with_responses):
    study, *_ = private_study_with_responses
    r = staff_client.get(reverse('study-download-responses', args=[study.id]))
    assert r.status_code == 200
    assert len(r.content.decode().splitlines()) == 3
