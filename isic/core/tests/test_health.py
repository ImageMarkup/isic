import pytest

from isic.core.health import check_engagement_profile_defaults_consistent, run_all_health_checks


@pytest.mark.django_db
def test_health_checks_run():
    # this is just a smoke test to verify these run in their default state
    run_all_health_checks()


@pytest.mark.django_db
def test_engagement_profile_defaults_inconsistent(
    engagement_profile_factory, cohort_factory, contributor_factory
):
    engagement_profile_factory(
        default_contributor=contributor_factory(), default_cohort=cohort_factory()
    )

    result = check_engagement_profile_defaults_consistent()
    assert not result.passed
    assert "1 engagement profiles" in result.message
