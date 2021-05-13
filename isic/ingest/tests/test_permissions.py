from django.urls.base import reverse
import pytest

from isic.factories import UserFactory
from isic.ingest.tests.factories import CohortFactory, ContributorFactory


@pytest.mark.django_db
def test_upload_select_contributor_permissions(client, staff_client):
    c1, c2, c3 = ContributorFactory(), ContributorFactory(), ContributorFactory()

    r = client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 302

    client.force_login(c1.creator)
    r = client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 200
    assert list(r.context['contributors'].values_list('pk', flat=True)) == [c1.pk]

    r = staff_client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 200
    assert list(r.context['contributors'].values_list('pk', flat=True)) == [c1.pk, c2.pk, c3.pk]


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['ingest-review', 'cohort-list'])
def test_staff_page_permissions(url_name, client, user_client, staff_client):
    r = client.get(reverse(url_name))
    assert r.status_code == 302

    r = user_client.get(reverse(url_name))
    assert r.status_code == 302

    r = staff_client.get(reverse(url_name))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('url_name', ['upload/cohort-files', 'upload-zip', 'upload-metadata'])
def test_cohort_pages_permissions(url_name, client, user_client, staff_client):
    # forcibly set the cohort creator to be different than the contributor creator,
    # since cohort permissions should be based on the contributor creator
    cohort = CohortFactory(creator=UserFactory())
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = user_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 404

    # scope permissions to the contributor, not the cohort creator
    client.force_login(cohort.creator)
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 404

    client.force_login(cohort.contributor.creator)
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 200

    r = staff_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'url_name',
    [
        'cohort-detail',
        'cohort-review-diagnosis',
        'cohort-review-quality-and-phi',
        'cohort-review-duplicate',
        'cohort-review-lesion',
    ],
)
def test_cohort_review_permissions(url_name, client, user_client, staff_client):
    cohort = CohortFactory()
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = user_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    client.force_login(cohort.contributor.creator)
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 200
