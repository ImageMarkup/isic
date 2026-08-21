from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.fixture
def unreviewed_engagement_accessions(
    cohort_factory, accession_factory, accession_review_factory, engagement_accession_factory
):
    """Unreviewed engagement accessions in two cohorts, among accessions the review must skip."""
    cohorts = [cohort_factory(), cohort_factory()]
    unreviewed = [
        engagement_accession_factory(
            accession=accession_factory(cohort=cohort, ingested=True)
        ).accession
        for cohort in cohorts
    ]

    # an engagement accession that staff already reviewed, and an accession that never came from
    # the engagement platform.
    engagement_accession_factory(
        accession=accession_review_factory(
            accession=accession_factory(cohort=cohorts[0], ingested=True), value=True
        ).accession
    )
    accession_factory(cohort=cohorts[0], ingested=True)

    return unreviewed


@pytest.mark.django_db
def test_engagement_accession_review(staff_client, unreviewed_engagement_accessions):
    r = staff_client.get(reverse("engagement/accession-review"))
    assert r.status_code == 200

    # every unreviewed engagement accession is shown, no matter which cohort it belongs to.
    assert {accession.pk for accession in r.context["page_obj"]} == {
        accession.pk for accession in unreviewed_engagement_accessions
    }

    num_unreviewed = len(unreviewed_engagement_accessions)
    assert r.context["progress"]["num_unreviewed"] == num_unreviewed
    assert r.context["progress"]["num_reviewed"] == 1
    # the reviewed engagement accession counts towards progress, the non engagement one does not.
    assert r.context["progress"]["num_reviewable"] == num_unreviewed + 1


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
def test_engagement_accession_review_permissions(client_, expected_status):
    r = client_.get(reverse("engagement/accession-review"))
    assert r.status_code == expected_status
