import pytest
from pytest_lazyfixture import lazy_fixture


@pytest.fixture()
def other_cohort(user_factory, cohort_factory):
    user = user_factory()
    return cohort_factory(contributor__owners=[user])


@pytest.fixture()
def cohorts(cohort, other_cohort):
    return [cohort, other_cohort]


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "cohorts_", "num_visible"),
    [
        (lazy_fixture("client"), lazy_fixture("cohorts"), 0),
        (lazy_fixture("authenticated_client"), lazy_fixture("cohorts"), 1),
        (lazy_fixture("staff_client"), lazy_fixture("cohorts"), 2),
    ],
    ids=[
        "guest",
        "user",
        "staff",
    ],
)
def test_core_api_cohort_list_permissions(client_, cohorts_, num_visible):
    r = client_.get("/api/v2/cohorts/")

    assert r.status_code == 200, r.json()
    assert r.json()["count"] == num_visible


@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("client_", "cohort_", "visible"),
    [
        (lazy_fixture("client"), lazy_fixture("cohort"), False),
        (lazy_fixture("client"), lazy_fixture("other_cohort"), False),
        (lazy_fixture("authenticated_client"), lazy_fixture("cohort"), True),
        (lazy_fixture("authenticated_client"), lazy_fixture("other_cohort"), False),
        (lazy_fixture("staff_client"), lazy_fixture("cohort"), True),
        (lazy_fixture("staff_client"), lazy_fixture("other_cohort"), True),
    ],
    ids=[
        "guest-cohort-1-invisible",
        "guest-cohort-2-invisible",
        "user-owner-cohort-1-visible",
        "user-non-owner-cohort-2-invisible",
        "staff-cohort-1-visible",
        "staff-cohort-2-visible",
    ],
)
def test_core_api_cohort_detail_permissions(client_, cohort_, visible):
    r = client_.get(f"/api/v2/cohorts/{cohort_.pk}/")

    if visible:
        assert r.status_code == 200, r.json()
        assert r.json()["id"] == cohort_.id
    else:
        assert r.status_code == 404, r.json()
