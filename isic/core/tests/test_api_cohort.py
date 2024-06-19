import pytest
from pytest_lazy_fixtures import lf


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
        (lf("client"), lf("cohorts"), 0),
        (lf("authenticated_client"), lf("cohorts"), 1),
        (lf("staff_client"), lf("cohorts"), 2),
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
        (lf("client"), lf("cohort"), False),
        (lf("client"), lf("other_cohort"), False),
        (lf("authenticated_client"), lf("cohort"), True),
        (lf("authenticated_client"), lf("other_cohort"), False),
        (lf("staff_client"), lf("cohort"), True),
        (lf("staff_client"), lf("other_cohort"), True),
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
