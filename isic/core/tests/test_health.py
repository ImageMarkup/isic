import pytest

from isic.core.health import run_all_health_checks


@pytest.mark.django_db
def test_health_checks_run():
    # this is just a smoke test to verify these run in their default state
    run_all_health_checks()
