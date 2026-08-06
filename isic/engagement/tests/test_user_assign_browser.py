from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.ingest.models import Contributor


@pytest.mark.playwright
def test_engagement_user_assign(
    staff_authenticated_page, engagement_profile_factory, cohort, cohort_factory
):
    page = staff_authenticated_page
    engagement_profile = engagement_profile_factory()
    contributor = cohort.contributor
    # belongs to a different contributor, so it must never appear in the cohort select
    other_cohort = cohort_factory()

    page.goto(reverse("engagement/user-list"))

    expect(page.get_by_text("Needs assignment")).to_be_visible()
    page.get_by_role("link", name="Assign").click()

    expect(page.get_by_text(engagement_profile.user.email)).to_be_visible()
    expect(page.get_by_text("owner", exact=False).first).to_be_visible()

    # the create tab is rendered up front rather than fetched, so switching reveals its fields
    page.get_by_role("tab", name="Create new").click()
    expect(page.get_by_label("Institution Name")).to_be_visible()
    page.get_by_role("tab", name="Select existing").click()
    expect(page.get_by_label("Institution Name")).not_to_be_visible()

    # until a contributor is picked there's nothing to choose from
    cohort_select = page.get_by_label("Cohort", exact=True)
    expect(cohort_select).to_have_value("")
    expect(cohort_select.locator("option")).to_have_count(1)

    contributor_fieldset = page.get_by_role("group").filter(
        has=page.get_by_text("Contributor", exact=True)
    )
    contributor_fieldset.get_by_role("searchbox").press_sequentially(
        contributor.institution_name[:5], delay=50
    )
    contributor_fieldset.get_by_text(contributor.institution_name, exact=True).first.click()
    # the preview panel confirms the selection resolved to a real contributor
    expect(contributor_fieldset.get_by_text(contributor.institution_url).first).to_be_visible()

    # picking a contributor narrows the cohort select to that contributor's cohorts
    expect(cohort_select.locator("option")).to_have_text(["No cohort", cohort.name])
    expect(cohort_select.locator("option", has_text=other_cohort.name)).to_have_count(0)
    cohort_select.select_option(label=cohort.name)

    page.get_by_role("button", name="Save assignment").click()

    expect(
        page.get_by_text(f"Assigned defaults for {engagement_profile.user.email}")
    ).to_be_visible()

    engagement_profile.refresh_from_db()
    assert engagement_profile.default_contributor == contributor
    assert engagement_profile.default_cohort == cohort
    assert contributor.owners.contains(engagement_profile.user)

    # with the filter on by default the newly assigned user drops off the list
    expect(page.get_by_text("No engagement users need assignment")).to_be_visible()

    page.get_by_text("Only show users needing assignment").click()

    expect(page.get_by_role("cell", name=contributor.institution_name)).to_be_visible()
    expect(page.get_by_role("link", name=cohort.name)).to_be_visible()


@pytest.mark.playwright
def test_engagement_user_assign_create_requires_confirmation(
    staff_authenticated_page, engagement_profile_factory, contributor_factory, cohort_factory
):
    """Creating a contributor and cohort must not be possible without confirming both."""
    page = staff_authenticated_page
    engagement_profile = engagement_profile_factory()
    # built, not created, so the form is filled with generated values that don't yet exist
    new_contributor = contributor_factory.build()
    new_cohort = cohort_factory.build(contributor=None, creator=None)

    page.goto(reverse("engagement/user-assign", args=[engagement_profile.pk]))
    page.get_by_role("tab", name="Create new").click()

    expect(page.get_by_text("new contributor", exact=False).first).to_be_visible()

    page.get_by_label("Institution Name").fill(new_contributor.institution_name)
    page.get_by_label("Legal Contact Information").fill(new_contributor.legal_contact_info)
    page.get_by_label("Default Attribution").fill(new_cohort.default_attribution)
    page.get_by_label("Cohort Name").fill(new_cohort.name)
    page.get_by_label("Cohort Description").fill(new_cohort.description)
    page.get_by_label("Default Copyright License").select_option(
        new_cohort.default_copyright_license
    )

    page.get_by_role("button", name="Create and assign").click()

    # the confirmation names both objects, and backing out of it creates neither
    confirm = page.get_by_role("dialog")
    expect(confirm.get_by_text(new_contributor.institution_name)).to_be_visible()
    expect(confirm.get_by_text(new_cohort.name)).to_be_visible()
    confirm.get_by_role("button", name="Cancel").click()

    assert not Contributor.objects.filter(
        institution_name=new_contributor.institution_name
    ).exists()

    page.get_by_role("button", name="Create and assign").click()
    page.get_by_role("button", name="Yes, create both").click()

    expect(
        page.get_by_text(f"Assigned defaults for {engagement_profile.user.email}")
    ).to_be_visible()

    engagement_profile.refresh_from_db()
    contributor = Contributor.objects.get(institution_name=new_contributor.institution_name)
    assert engagement_profile.default_contributor == contributor
    assert engagement_profile.default_cohort == contributor.cohorts.get(name=new_cohort.name)


@pytest.mark.playwright
def test_engagement_user_assign_accepts_suggestion_unchanged(
    staff_authenticated_page, engagement_profile_factory, email_domain_contributor, cohort_factory
):
    """A suggested contributor and cohort must survive submission without being touched."""
    page = staff_authenticated_page
    engagement_profile = engagement_profile_factory()
    engagement_profile.user.emailaddress_set.filter(primary=True).update(
        email=f"someone@{email_domain_contributor.domain}"
    )
    cohort = cohort_factory(contributor=email_domain_contributor.contributor)

    page.goto(reverse("engagement/user-assign", args=[engagement_profile.pk]))

    # the sole cohort is preselected, not merely present among the options
    expect(page.get_by_label("Cohort", exact=True)).to_have_value(str(cohort.pk))

    page.get_by_role("button", name="Save assignment").click()

    expect(
        page.get_by_text(f"Assigned defaults for {engagement_profile.user.email}")
    ).to_be_visible()

    engagement_profile.refresh_from_db()
    assert engagement_profile.default_contributor == email_domain_contributor.contributor
    assert engagement_profile.default_cohort == cohort
