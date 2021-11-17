from django.urls.base import reverse
import pytest


@pytest.mark.django_db
def test_upload_select_contributor_permissions(
    client, authenticated_client, staff_client, contributor_factory
):
    c1, c2, c3 = contributor_factory(), contributor_factory(), contributor_factory()

    r = client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 302  # redirect to login page

    r = authenticated_client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 302  # redirect to create-contributor page

    client.force_login(c1.creator)
    r = client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 200
    assert set(r.context['contributors'].values_list('pk', flat=True)) == {c1.pk}

    r = staff_client.get(reverse('upload/select-or-create-contributor'))
    assert r.status_code == 200
    assert set(r.context['contributors'].values_list('pk', flat=True)) == {c1.pk, c2.pk, c3.pk}


@pytest.mark.django_db
def test_upload_create_contributor_permissions(client, authenticated_client):
    r = client.get(reverse('upload/create-contributor'))
    assert r.status_code == 302  # redirect to login page

    r = authenticated_client.get(reverse('upload/create-contributor'))
    assert r.status_code == 200


@pytest.mark.django_db
def test_upload_select_create_cohort_permissions(
    client, authenticated_client, staff_client, cohort_factory, contributor_factory
):
    contributor1, contributor2 = contributor_factory(), contributor_factory()
    cohort_factory(contributor=contributor1)
    cohort_factory(contributor=contributor2)

    for contributor in [contributor1, contributor2]:
        r = client.get(reverse('upload/select-or-create-cohort', args=[contributor.pk]))
        assert r.status_code == 404

        r = authenticated_client.get(
            reverse('upload/select-or-create-cohort', args=[contributor.pk])
        )
        assert r.status_code == 404

        client.force_login(contributor.creator)
        r = client.get(reverse('upload/select-or-create-cohort', args=[contributor.pk]))
        assert r.status_code == 200
        assert set(r.context['cohorts']) == set(list(contributor.cohorts.all()))

        r = staff_client.get(reverse('upload/select-or-create-cohort', args=[contributor.pk]))
        assert r.status_code == 200
        assert set(r.context['cohorts']) == set(list(contributor.cohorts.all()))


@pytest.mark.django_db
def test_upload_create_cohort_permissions(client, authenticated_client, contributor_factory, user):
    contributor = contributor_factory(creator=user)

    r = client.get(reverse('upload/create-cohort', args=[contributor.pk]))
    assert r.status_code == 302  # redirect to login page

    r = authenticated_client.get(reverse('upload/create-cohort', args=[contributor.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_staff_page_permissions(client, authenticated_client, staff_client):
    r = client.get(reverse('ingest-review'))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('ingest-review'))
    assert r.status_code == 302

    r = staff_client.get(reverse('ingest-review'))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    'url_name', ['upload/cohort-files', 'upload-zip', 'upload-metadata', 'upload/cohort-browser']
)
def test_cohort_pages_permissions(
    url_name, client, authenticated_client, staff_client, cohort_factory, user_factory
):
    # forcibly set the cohort creator to be different than the contributor creator,
    # since cohort permissions should be based on the contributor creator
    cohort = cohort_factory(creator=user_factory())
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse(url_name, args=[cohort.pk]))
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
def test_cohort_review_permissions(url_name, client, authenticated_client, staff_client, cohort):
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    client.force_login(cohort.contributor.creator)
    r = client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse(url_name, args=[cohort.pk]))
    assert r.status_code == 200


@pytest.mark.django_db
def test_reset_metadata_permissions(client, authenticated_client, staff_client, cohort):
    r = client.get(reverse('reset-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    client.force_login(cohort.contributor.creator)
    r = client.get(reverse('reset-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('reset-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    # TODO: how to handle redirects generally since they're a bad indicator for 'access denied'
    # in tests
    r = staff_client.get(reverse('reset-metadata', args=[cohort.pk]))
    assert r.status_code == 302
    # 302s on a successful page load, so test where it's redirecting as a proxy for access
    assert r.url == reverse('cohort-detail', args=[cohort.pk])


@pytest.mark.django_db
def test_validate_metadata_permissions(client, authenticated_client, staff_client, cohort):
    r = client.get(reverse('validate-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    client.force_login(cohort.contributor.creator)
    r = client.get(reverse('validate-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    r = authenticated_client.get(reverse('validate-metadata', args=[cohort.pk]))
    assert r.status_code == 302

    r = staff_client.get(reverse('validate-metadata', args=[cohort.pk]))
    assert r.status_code == 200

    r = staff_client.get(reverse('validate-metadata', args=[cohort.pk]))
    assert r.status_code == 200
