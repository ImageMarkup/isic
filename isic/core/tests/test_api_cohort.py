from django.urls import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.fixture
def other_cohort(user_factory, cohort_factory):
    user = user_factory()
    return cohort_factory(contributor__owners=[user])


@pytest.fixture
def cohorts(cohort, other_cohort):
    return [cohort, other_cohort]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "cohorts_", "num_visible"),
    [
        (lf("client"), lf("cohorts"), None),
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
    r = client_.get(reverse("api:cohort_list"))

    if num_visible is None:
        assert r.status_code == 401, r.json()
    else:
        assert r.status_code == 200, r.json()
        assert r.json()["count"] == num_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "cohort_", "expected_status"),
    [
        (lf("client"), lf("cohort"), 401),
        (lf("client"), lf("other_cohort"), 401),
        (lf("authenticated_client"), lf("cohort"), 200),
        (lf("authenticated_client"), lf("other_cohort"), 404),
        (lf("staff_client"), lf("cohort"), 200),
        (lf("staff_client"), lf("other_cohort"), 200),
    ],
    ids=[
        "guest-cohort-1-unauthorized",
        "guest-cohort-2-unauthorized",
        "user-owner-cohort-1-visible",
        "user-non-owner-cohort-2-invisible",
        "staff-cohort-1-visible",
        "staff-cohort-2-visible",
    ],
)
def test_core_api_cohort_detail_permissions(client_, cohort_, expected_status):
    r = client_.get(reverse("api:cohort_detail", kwargs={"id": cohort_.pk}))

    assert r.status_code == expected_status, r.json()

    if expected_status == 200:
        assert r.json()["id"] == cohort_.id
