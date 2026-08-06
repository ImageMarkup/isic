from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.models import Cohort, Contributor


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
def test_engagement_user_assign_permissions(client_, expected_status, engagement_profile):
    r = client_.get(reverse("engagement/user-assign", args=[engagement_profile.pk]))
    assert r.status_code == expected_status


@pytest.mark.django_db
def test_engagement_user_assign_existing(staff_client, engagement_profile, cohort, cohort_factory):
    other_cohort = cohort_factory()
    url = reverse("engagement/user-assign", args=[engagement_profile.pk])

    # a contributor with no cohort is a valid half provisioned state
    r = staff_client.post(
        url, data={"action": "select_existing", "contributor": cohort.contributor.pk}
    )

    assert r.status_code == 302
    assert r.url == reverse("engagement/user-list")
    engagement_profile.refresh_from_db()
    assert engagement_profile.default_contributor == cohort.contributor
    assert engagement_profile.default_cohort is None
    # assignment is what makes the user able to upload into the contributor's cohorts
    assert cohort.contributor.owners.contains(engagement_profile.user)

    # a cohort belonging to a different contributor is rejected and changes nothing
    r = staff_client.post(
        url,
        data={
            "action": "select_existing",
            "contributor": cohort.contributor.pk,
            "cohort": other_cohort.pk,
        },
    )

    assert r.status_code == 200
    assert "belongs to" in r.content.decode()
    engagement_profile.refresh_from_db()
    assert engagement_profile.default_cohort is None
    assert not other_cohort.contributor.owners.contains(engagement_profile.user)

    r = staff_client.post(
        url,
        data={
            "action": "select_existing",
            "contributor": cohort.contributor.pk,
            "cohort": cohort.pk,
        },
    )

    assert r.status_code == 302
    engagement_profile.refresh_from_db()
    assert engagement_profile.default_cohort == cohort


@pytest.mark.django_db
def test_engagement_user_assign_create(
    staff_client, engagement_profile, contributor_factory, cohort_factory
):
    # built, not created, so the payload carries generated values without persisting anything
    new_contributor = contributor_factory.build()
    new_cohort = cohort_factory.build(contributor=None, creator=None)
    url = reverse("engagement/user-assign", args=[engagement_profile.pk])

    r = staff_client.post(
        url,
        data={
            "action": "create_new",
            "institution_name": new_contributor.institution_name,
            "legal_contact_info": new_contributor.legal_contact_info,
            "default_attribution": new_cohort.default_attribution,
            "cohort_name": new_cohort.name,
            "cohort_description": new_cohort.description,
            "cohort_default_copyright_license": new_cohort.default_copyright_license,
        },
    )

    assert r.status_code == 302, r.context["create_form"].errors
    assert r.url == reverse("engagement/user-list")

    engagement_profile.refresh_from_db()
    contributor = Contributor.objects.get()
    cohort = Cohort.objects.get()

    assert contributor.institution_name == new_contributor.institution_name
    assert contributor.legal_contact_info == new_contributor.legal_contact_info
    assert cohort.contributor == contributor
    assert cohort.name == new_cohort.name
    assert cohort.default_copyright_license == new_cohort.default_copyright_license
    # the form only asks for attribution once, at the institution level
    assert contributor.default_attribution == new_cohort.default_attribution
    assert cohort.default_attribution == contributor.default_attribution
    assert engagement_profile.default_contributor == contributor
    assert engagement_profile.default_cohort == cohort
    assert contributor.owners.contains(engagement_profile.user)

    # an incomplete submission creates nothing and reopens the tab it was submitted from
    r = staff_client.post(url, data={"action": "create_new", "institution_name": "Some Institute"})

    assert r.status_code == 200
    assert r.context["mode"] == "create_new"
    assert Contributor.objects.count() == 1
    assert Cohort.objects.count() == 1


@pytest.mark.django_db
def test_engagement_user_assign_prefills_suggestion(
    staff_client, engagement_profile, email_domain_contributor, cohort_factory
):
    engagement_profile.user.emailaddress_set.filter(primary=True).update(
        email=f"someone@{email_domain_contributor.domain}"
    )
    url = reverse("engagement/user-assign", args=[engagement_profile.pk])

    r = staff_client.get(url)

    assert r.status_code == 200
    assert r.context["suggested_contributor"] == email_domain_contributor.contributor
    assert r.context["existing_form"].initial["contributor"] == email_domain_contributor.contributor
    # the contributor has no cohorts yet, so there's nothing to suggest or select
    assert r.context["existing_form"].initial["cohort"] is None
    assert r.context["initial_cohorts"] == []

    cohort = cohort_factory(contributor=email_domain_contributor.contributor)
    # a cohort under someone else must never reach the select
    cohort_factory()
    r = staff_client.get(url)

    assert r.context["existing_form"].initial["cohort"] == cohort
    assert r.context["initial_cohorts"] == [{"id": cohort.pk, "name": cohort.name}]

    # a second cohort makes the choice ambiguous, so no cohort is suggested, but both are
    # still offered in the select
    second_cohort = cohort_factory(contributor=email_domain_contributor.contributor)
    r = staff_client.get(url)

    assert r.context["suggested_contributor"] == email_domain_contributor.contributor
    assert r.context["existing_form"].initial["cohort"] is None
    assert {option["id"] for option in r.context["initial_cohorts"]} == {
        cohort.pk,
        second_cohort.pk,
    }
