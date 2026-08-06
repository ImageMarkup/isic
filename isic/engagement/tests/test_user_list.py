from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.django_db
def test_engagement_user_list(
    staff_client, engagement_profile_factory, email_domain_contributor_factory, contributor
):
    provisioned_profile = engagement_profile_factory(provisioned=True)
    bare_profile = engagement_profile_factory()
    # a contributor without a cohort is only half provisioned, so it still needs assignment
    cohortless_profile = engagement_profile_factory(default_contributor=contributor)
    suggestable_profile = engagement_profile_factory()
    email_domain_contributor = email_domain_contributor_factory()
    suggestable_profile.user.emailaddress_set.filter(primary=True).update(
        email=f"someone@{email_domain_contributor.domain}"
    )

    # the filter defaults on, so only the users still needing provisioning are listed
    r = staff_client.get(reverse("engagement/user-list"))
    assert r.status_code == 200

    suggestions_by_pk = {profile.pk: suggestion for profile, suggestion in r.context["rows"]}
    assert set(suggestions_by_pk) == {
        bare_profile.pk,
        cohortless_profile.pk,
        suggestable_profile.pk,
    }
    assert suggestions_by_pk[suggestable_profile.pk] == email_domain_contributor.contributor
    assert suggestions_by_pk[bare_profile.pk] is None

    content = r.content.decode()
    assert "Suggestion ready" in content
    assert "Needs assignment" in content
    assert "Needs cohort" in content
    assert bare_profile.user.email in content

    # turning it off reveals the users that have already been assigned
    r = staff_client.get(reverse("engagement/user-list"), {"only_unassigned": "0"})
    assert r.status_code == 200

    profile_pks = {profile.pk for profile in r.context["page"]}
    assert profile_pks == {
        provisioned_profile.pk,
        bare_profile.pk,
        cohortless_profile.pk,
        suggestable_profile.pk,
    }

    content = r.content.decode()
    assert provisioned_profile.default_cohort.name in content
    assert provisioned_profile.default_contributor.institution_name in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "expected_status"),
    [
        (lf("client"), 302),
        (lf("authenticated_client"), 302),
        (lf("staff_client"), 200),
    ],
    ids=["anonymous", "authenticated", "staff"],
)
def test_engagement_user_list_permissions(client_, expected_status):
    r = client_.get(reverse("engagement/user-list"))
    assert r.status_code == expected_status
