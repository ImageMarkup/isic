from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_engagement_api_profile(authenticated_client, user, engagement_profile_factory):
    profile = engagement_profile_factory(user=user, provisioned=True)

    r = authenticated_client.get(reverse("api:engagement_profile"))

    assert r.status_code == 200, r.json()
    assert r.json()["default_contributor"] == profile.default_contributor.pk
    assert r.json()["default_cohort"] == profile.default_cohort.pk


@pytest.mark.django_db
def test_engagement_api_profile_unprovisioned(
    authenticated_client, user, engagement_profile_factory
):
    engagement_profile_factory(user=user)

    r = authenticated_client.get(reverse("api:engagement_profile"))

    assert r.status_code == 200, r.json()
    assert r.json()["default_contributor"] is None
    assert r.json()["default_cohort"] is None


@pytest.mark.django_db
def test_engagement_api_profile_non_engagement_user(authenticated_client):
    r = authenticated_client.get(reverse("api:engagement_profile"))

    assert r.status_code == 404, r.json()


@pytest.mark.django_db
def test_engagement_api_profile_unauthenticated(client):
    r = client.get(reverse("api:engagement_profile"))

    assert r.status_code == 401, r.json()
