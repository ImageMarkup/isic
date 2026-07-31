from django.urls import reverse
import pytest


@pytest.mark.django_db
def test_api_contributor_detail_counts(
    staff_client, contributor_factory, cohort_factory, accession_factory
):
    contributor = contributor_factory()
    cohort = cohort_factory(contributor=contributor)
    accession_factory(cohort=cohort)
    accession_factory(cohort=cohort)
    empty_cohort = cohort_factory(contributor=contributor)
    # a second contributor's accessions shouldn't be counted
    accession_factory(cohort=cohort_factory())

    resp = staff_client.get(reverse("api:contributor_detail", args=[contributor.pk]))

    assert resp.status_code == 200, resp.json()
    assert resp.json()["cohort_count"] == 2
    assert resp.json()["accession_count"] == 2
    # cohorts are inlined, ordered by descending accession count
    assert resp.json()["cohorts"] == [
        {"id": cohort.pk, "name": cohort.name, "accession_count": 2},
        {"id": empty_cohort.pk, "name": empty_cohort.name, "accession_count": 0},
    ]


@pytest.mark.django_db
def test_api_contributor_autocomplete(staff_client, contributor_factory):
    contributor = contributor_factory(institution_name="Institute of Dermatology")
    contributor_factory(institution_name="Unrelated Hospital")

    resp = staff_client.get(reverse("api:contributor_autocomplete"), data={"query": "Dermatology"})

    assert resp.status_code == 200, resp.json()
    assert [c["id"] for c in resp.json()] == [contributor.pk]
    # only what's needed to render a suggestion, private fields aren't exposed to autocomplete
    assert set(resp.json()[0]) == {"id", "institution_name"}


@pytest.mark.django_db
def test_api_contributor_autocomplete_only_returns_visible_contributors(
    authenticated_client, user, contributor_factory
):
    owned = contributor_factory(institution_name="Institute of Dermatology", owners=[user])
    contributor_factory(institution_name="Other Institute of Dermatology")

    resp = authenticated_client.get(
        reverse("api:contributor_autocomplete"), data={"query": "Dermatology"}
    )

    assert resp.status_code == 200, resp.json()
    assert [c["id"] for c in resp.json()] == [owned.pk]
