from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.core.models.image import Image
from isic.ingest.models.publish_request import PublishRequest


@pytest.fixture
def publishable_engagement_accessions(
    cohort_factory, accession_review_factory, engagement_accession_factory
):
    """One accepted engagement platform accession in each of two cohorts, keyed by cohort."""
    accessions = {}

    for _ in range(2):
        cohort = cohort_factory()
        accession = accession_review_factory(
            accession__cohort=cohort, accession__ingested=True, value=True
        ).accession
        engagement_accession_factory(accession=accession)
        accessions[cohort] = accession

    return accessions


@pytest.mark.django_db
@pytest.mark.usefixtures("_search_index")
def test_engagement_accession_publish(
    staff_client,
    publishable_engagement_accessions,
    accession_review_factory,
    collection_factory,
    django_capture_on_commit_callbacks,
):
    cohorts = list(publishable_engagement_accessions)
    # an accepted accession in one of the same cohorts that didn't come from the engagement
    # platform. publishing from this page has to leave it alone.
    other_accession = accession_review_factory(
        accession__cohort=cohorts[0], accession__ingested=True, value=True
    ).accession
    collection = collection_factory(public=False)

    r = staff_client.get(reverse("engagement/accession-publish"))
    assert r.status_code == 200
    assert r.context["num_publishable"] == len(publishable_engagement_accessions)
    assert {row["cohort_id"] for row in r.context["cohorts"]} == {cohort.pk for cohort in cohorts}

    with django_capture_on_commit_callbacks(execute=True):
        r = staff_client.post(
            reverse("engagement/accession-publish"),
            {"additional_collections": [collection.pk]},
        )
    assert r.status_code == 302

    # a publish request per cohort, each carrying its own cohort's attribution and only its own
    # cohort's engagement accessions.
    publish_requests = list(PublishRequest.objects.all())
    assert len(publish_requests) == len(cohorts)
    assert {publish_request.default_attribution for publish_request in publish_requests} == {
        cohort.default_attribution for cohort in cohorts
    }
    assert {
        accession.pk
        for publish_request in publish_requests
        for accession in publish_request.accessions.all()
    } == {accession.pk for accession in publishable_engagement_accessions.values()}

    published = Image.objects.filter(accession__in=publishable_engagement_accessions.values())
    assert published.count() == len(publishable_engagement_accessions)
    # publishing from the engagement page unembargoes in the same step, so the images are public
    # and their blobs have moved to the sponsored bucket.
    assert not published.filter(public=False).exists()
    assert not published.filter(accession__sponsored_blob="").exists()
    assert not Image.objects.filter(accession=other_accession).exists()

    assert collection.images.count() == len(publishable_engagement_accessions)
    for cohort, accession in publishable_engagement_accessions.items():
        cohort.refresh_from_db()
        assert cohort.collection.images.get().accession_id == accession.pk


@pytest.mark.django_db
@pytest.mark.usefixtures("engagement_accessions_by_state")
def test_engagement_accession_publish_counts_only_accepted(staff_client):
    # of every state an engagement accession can be in, only the accepted one is publishable.
    r = staff_client.get(reverse("engagement/accession-list"))
    assert r.context["num_publishable"] == 1

    r = staff_client.get(reverse("engagement/accession-publish"))
    assert r.context["num_publishable"] == 1


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
def test_engagement_accession_publish_permissions(client_, expected_status):
    r = client_.get(reverse("engagement/accession-publish"))
    assert r.status_code == expected_status
