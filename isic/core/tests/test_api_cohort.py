import pytest
from pytest import lazy_fixture


@pytest.fixture
def other_cohort(user_factory, cohort_factory):
    user = user_factory()
    cohort = cohort_factory(contributor__owners=[user])
    return cohort


@pytest.fixture
def cohorts(cohort, other_cohort):
    return [cohort, other_cohort]


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client,cohorts_,num_visible',
    [
        [lazy_fixture('api_client'), lazy_fixture('cohorts'), 0],
        [lazy_fixture('authenticated_api_client'), lazy_fixture('cohorts'), 1],
        [lazy_fixture('staff_api_client'), lazy_fixture('cohorts'), 2],
    ],
    ids=[
        'guest',
        'user',
        'staff',
    ],
)
def test_core_api_cohort_list_permissions(client, cohorts_, num_visible):
    r = client.get('/api/v2/cohorts/')

    assert r.status_code == 200, r.data
    assert r.data['count'] == num_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    'client,cohort_,visible',
    [
        [lazy_fixture('api_client'), lazy_fixture('cohort'), False],
        [lazy_fixture('api_client'), lazy_fixture('other_cohort'), False],
        [lazy_fixture('authenticated_api_client'), lazy_fixture('cohort'), True],
        [lazy_fixture('authenticated_api_client'), lazy_fixture('other_cohort'), False],
        [lazy_fixture('staff_api_client'), lazy_fixture('cohort'), True],
        [lazy_fixture('staff_api_client'), lazy_fixture('other_cohort'), True],
    ],
    ids=[
        'guest-cohort-1-invisible',
        'guest-cohort-2-invisible',
        'user-owner-cohort-1-visible',
        'user-non-owner-cohort-2-invisible',
        'staff-cohort-1-visible',
        'staff-cohort-2-visible',
    ],
)
def test_core_api_cohort_detail_permissions(client, cohort_, visible):
    r = client.get(f'/api/v2/cohorts/{cohort_.pk}/')

    if visible:
        assert r.status_code == 200, r.data
        assert r.data['id'] == cohort_.id
    else:
        assert r.status_code == 404, r.data


@pytest.mark.django_db
def test_core_api_cohort_create(authenticated_api_client, user, contributor):
    r = authenticated_api_client.post(
        '/api/v2/cohorts/',
        data={
            'contributor': contributor.pk,
            'name': 'string',
            'description': 'string',
            'copyright_license': 'CC-0',
            'attribution': 'string',
        },
    )
    assert r.status_code == 201, r.data
    assert r.data['creator'] == user.pk


@pytest.mark.django_db
def test_core_api_cohort_create_invalid_contributor(
    authenticated_api_client, user, other_contributor
):
    r = authenticated_api_client.post(
        '/api/v2/cohorts/',
        data={
            'contributor': other_contributor.pk,
            'name': 'string',
            'description': 'string',
            'copyright_license': 'CC-0',
            'attribution': 'string',
        },
    )
    assert r.status_code == 403, r.data
