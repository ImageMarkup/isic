import pytest

from isic.engagement.models import EngagementProfile


@pytest.mark.django_db
def test_engagement_profile_created_for_engagement_app(user, engagement_app, grant_token):
    grant_token(user, engagement_app)

    profile = EngagementProfile.objects.get(user=user)
    assert profile.default_contributor is None
    assert profile.default_cohort is None


@pytest.mark.django_db
def test_engagement_profile_not_created_for_other_app(
    user, engagement_app, other_oauth_app, grant_token
):
    grant_token(user, other_oauth_app)

    assert not EngagementProfile.objects.exists()


@pytest.mark.django_db
def test_engagement_profile_not_created_when_setting_unset(
    user, oauth_app_factory, grant_token, settings
):
    settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID = None
    app = oauth_app_factory("Some app")

    grant_token(user, app)

    assert not EngagementProfile.objects.exists()


@pytest.mark.django_db
def test_engagement_profile_preserves_existing_defaults(
    user, engagement_app, grant_token, engagement_profile_factory
):
    profile = engagement_profile_factory(user=user, provisioned=True)

    grant_token(user, engagement_app)

    contributor, cohort = profile.default_contributor, profile.default_cohort
    profile.refresh_from_db()
    assert profile.default_contributor == contributor
    assert profile.default_cohort == cohort
