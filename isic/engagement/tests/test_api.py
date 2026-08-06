from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_engagement_api_profile(authenticated_client, user, engagement_profile_factory):
    profile = engagement_profile_factory(user=user, provisioned=True)

    r = authenticated_client.get(reverse("api:engagement_profile"))

    assert r.status_code == 200, r.json()

    contributor_json = r.json()["default_contributor"]
    assert contributor_json.pop("created")
    assert contributor_json == {
        "id": profile.default_contributor.pk,
        "creator": profile.default_contributor.creator_id,
        "owners": [owner.pk for owner in profile.default_contributor.owners.all()],
        "institution_name": profile.default_contributor.institution_name,
        "institution_url": profile.default_contributor.institution_url,
        "legal_contact_info": profile.default_contributor.legal_contact_info,
        "default_copyright_license": profile.default_contributor.default_copyright_license,
        "default_attribution": profile.default_contributor.default_attribution,
    }

    cohort_json = r.json()["default_cohort"]
    assert cohort_json.pop("created")
    assert cohort_json == {
        "id": profile.default_cohort.pk,
        "creator": profile.default_cohort.creator_id,
        "contributor": profile.default_cohort.contributor_id,
        "name": profile.default_cohort.name,
        "description": profile.default_cohort.description,
        "default_copyright_license": profile.default_cohort.default_copyright_license,
        "default_attribution": profile.default_cohort.default_attribution,
        "accession_count": profile.default_cohort.accessions.count(),
    }


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
