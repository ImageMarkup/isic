from django.urls import reverse
from playwright.sync_api import expect
import pytest

from isic.ingest.models import Contributor


@pytest.fixture
def contributor_with_cohorts(contributor_factory, cohort_factory, user_factory):
    def _contributor_with_cohorts(num_cohorts: int = 1):
        user = user_factory()
        contributor = contributor_factory(creator=user, owners=[user])
        for _ in range(num_cohorts):
            cohort_factory(contributor=contributor, creator=user)
        return contributor

    return _contributor_with_cohorts


@pytest.mark.playwright
def test_merge_contributors_autocomplete_preview_and_submit(
    staff_authenticated_page, contributor_with_cohorts
):
    page = staff_authenticated_page

    contributor_a = contributor_with_cohorts(num_cohorts=2)
    contributor_b = contributor_with_cohorts()
    contributor_b_cohorts = set(contributor_b.cohorts.values_list("pk", flat=True))

    page.goto(reverse("ingest/merge-contributors"))

    expect(page.get_by_text("Merge Contributors").first).to_be_visible()

    # Type in the first autocomplete field to search for contributor_a
    first_fieldset = page.get_by_role("group").filter(has_text="Contributor to merge into")
    first_input = first_fieldset.get_by_role("searchbox")
    first_input.press_sequentially(contributor_a.institution_name[:5], delay=50)

    # Wait for autocomplete results and select contributor_a. The lookup is scoped to the
    # fieldset since the other field's preview panel also renders the institution name.
    first_result = first_fieldset.get_by_text(contributor_a.institution_name, exact=True).first
    expect(first_result).to_be_visible()
    first_result.click()

    # Preview should show contributor details, including each of its cohorts
    expect(first_fieldset.get_by_text(contributor_a.institution_url).first).to_be_visible()
    for cohort in contributor_a.cohorts.all():
        expect(first_fieldset.get_by_text(cohort.name).first).to_be_visible()

    # Type in the second autocomplete field to search for contributor_b
    second_fieldset = page.get_by_role("group").filter(
        has_text="Contributor to merge", has_not_text="Contributor to merge into"
    )
    second_input = second_fieldset.get_by_role("searchbox")
    second_input.press_sequentially(contributor_b.institution_name[:5], delay=50)

    # Wait for autocomplete results and select contributor_b
    second_result = second_fieldset.get_by_text(contributor_b.institution_name, exact=True).first
    expect(second_result).to_be_visible()
    second_result.click()

    # Preview should show contributor_b details
    expect(page.get_by_text(contributor_b.institution_url).first).to_be_visible()

    # Submit the merge
    page.get_by_role("button", name="Merge Contributors").click()

    # Should redirect to the cohort list page with a success flash message
    page.wait_for_url(f"**{reverse('ingest/cohort-list')}")
    expect(page.get_by_text("Contributor merged successfully.")).to_be_visible()

    # Verify contributor_b was deleted and its cohorts moved to contributor_a
    assert not Contributor.objects.filter(pk=contributor_b.pk).exists()
    assert contributor_b_cohorts <= set(contributor_a.cohorts.values_list("pk", flat=True))


@pytest.mark.playwright
def test_merge_contributors_shows_access_impact(
    staff_authenticated_page,
    contributor_with_cohorts,
    accession_factory,
    image_factory,
    user_factory,
    engagement_profile_factory,
):
    page = staff_authenticated_page

    dest_contributor = contributor_with_cohorts()
    src_contributor = contributor_with_cohorts()

    # an owner of both contributors already sees everything, so they gain nothing from the merge
    shared_owner = user_factory()
    dest_contributor.owners.add(shared_owner)
    src_contributor.owners.add(shared_owner)
    dest_only_owner, src_only_owner = user_factory(), user_factory()
    dest_contributor.owners.add(dest_only_owner)
    src_contributor.owners.add(src_only_owner)

    dest_cohort = dest_contributor.cohorts.first()
    image_factory(accession=accession_factory(cohort=dest_cohort))
    accession_factory(cohort=dest_cohort)

    engagement_profile_factory(user=src_only_owner, default_contributor=src_contributor)
    engagement_profile_factory(default_contributor=src_contributor)

    page.goto(reverse("ingest/merge-contributors"))

    for fieldset_filter, contributor in [
        ({"has_text": "Contributor to merge into"}, dest_contributor),
        (
            {"has_text": "Contributor to merge", "has_not_text": "Contributor to merge into"},
            src_contributor,
        ),
    ]:
        fieldset = page.get_by_role("group").filter(**fieldset_filter)
        fieldset.get_by_role("searchbox").press_sequentially(
            contributor.institution_name[:5], delay=50
        )
        result = fieldset.get_by_text(contributor.institution_name, exact=True).first
        expect(result).to_be_visible()
        result.click()

    impact = page.get_by_role("alert")
    expect(impact.get_by_text("Access impact of this merge")).to_be_visible()

    # both directions are described, and the owner of both contributors is left out of them
    expect(impact.get_by_text(src_only_owner.email)).to_be_visible()
    expect(impact.get_by_text(dest_only_owner.email)).to_be_visible()
    expect(impact.get_by_text(shared_owner.email)).not_to_be_visible()

    expect(impact.get_by_text("engagement user")).to_be_visible()
    expect(impact.get_by_text("will also have access to every future upload")).to_be_visible()
    expect(impact.get_by_text("Their default will be repointed to")).to_be_visible()

    # clearing a contributor leaves nothing to describe
    second_fieldset = page.get_by_role("group").filter(
        has_text="Contributor to merge", has_not_text="Contributor to merge into"
    )
    second_fieldset.get_by_role("searchbox").fill("")
    expect(impact).not_to_be_visible()


@pytest.mark.playwright
def test_merge_contributors_same_contributor_rejected(
    staff_authenticated_page, contributor_with_cohorts
):
    page = staff_authenticated_page

    contributor = contributor_with_cohorts()

    page.goto(reverse("ingest/merge-contributors"))

    for fieldset_filter in [
        {"has_text": "Contributor to merge into"},
        {"has_text": "Contributor to merge", "has_not_text": "Contributor to merge into"},
    ]:
        fieldset = page.get_by_role("group").filter(**fieldset_filter)
        fieldset.get_by_role("searchbox").press_sequentially(
            contributor.institution_name[:5], delay=50
        )
        result = fieldset.get_by_text(contributor.institution_name, exact=True).first
        expect(result).to_be_visible()
        result.click()

    page.get_by_role("button", name="Merge Contributors").click()

    expect(page.get_by_text("The two contributors must be different.")).to_be_visible()
    assert Contributor.objects.filter(pk=contributor.pk).exists()
