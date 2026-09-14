from django.urls import reverse
import pytest
from pytest_lazy_fixtures import lf


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


@pytest.mark.django_db
def test_api_contributor_merge_impact(contributor_factory, user_factory, staff_client):
    src_owner = user_factory()
    dest_contributor = contributor_factory()
    src_contributor = contributor_factory(owners=[src_owner])

    resp = staff_client.get(
        reverse("api:contributor_merge_impact"),
        data={"dest_contributor": dest_contributor.pk, "src_contributor": src_contributor.pk},
    )

    assert resp.status_code == 200, resp.json()
    assert resp.json()["dest_contributor"]["id"] == dest_contributor.pk
    assert [u["email"] for u in resp.json()["users_gaining_access_to_dest"]] == [src_owner.email]


@pytest.mark.django_db
def test_api_contributor_merge_impact_same_contributor(contributor_factory, staff_client):
    contributor = contributor_factory()

    resp = staff_client.get(
        reverse("api:contributor_merge_impact"),
        data={"dest_contributor": contributor.pk, "src_contributor": contributor.pk},
    )

    assert resp.status_code == 400, resp.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("client_", "status_code"),
    [
        (lf("client"), 401),
        (lf("authenticated_client"), 401),
        (lf("staff_client"), 200),
    ],
)
def test_api_contributor_merge_impact_permissions(client_, status_code, contributor_factory):
    dest_contributor, src_contributor = contributor_factory(), contributor_factory()

    resp = client_.get(
        reverse("api:contributor_merge_impact"),
        data={"dest_contributor": dest_contributor.pk, "src_contributor": src_contributor.pk},
    )

    assert resp.status_code == status_code
