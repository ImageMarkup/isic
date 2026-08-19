from django.urls import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.models.accession import AccessionState, AccessionStatus


def post_list(client, filters: dict | None = None, **kwargs):
    return client.post(
        reverse("api:engagement_accession_list"),
        filters or {},
        content_type="application/json",
        **kwargs,
    )


@pytest.fixture
def service_headers(engagement_service_app, client_credentials_token):
    return {"Authorization": f"Bearer {client_credentials_token(engagement_service_app)}"}


@pytest.fixture
def accessions_by_state(
    cohort_factory,
    accession_factory,
    accession_review_factory,
    image_factory,
    engagement_accession_factory,
):
    cohort = cohort_factory()

    accessions = {
        AccessionState.PROCESSING: accession_factory(cohort=cohort),
        AccessionState.SKIPPED: accession_factory(cohort=cohort, status=AccessionStatus.SKIPPED),
        AccessionState.FAILED: accession_factory(cohort=cohort, status=AccessionStatus.FAILED),
        AccessionState.AWAITING_REVIEW: accession_factory(cohort=cohort, ingested=True),
        AccessionState.ACCEPTED: accession_review_factory(
            accession__cohort=cohort, accession__ingested=True, value=True
        ).accession,
        AccessionState.REJECTED: accession_review_factory(
            accession__cohort=cohort, accession__ingested=True, value=False
        ).accession,
        AccessionState.PUBLISHED: image_factory(public=True, accession__cohort=cohort).accession,
    }

    for accession in accessions.values():
        engagement_accession_factory(accession=accession)

    return cohort, accessions


@pytest.mark.django_db
def test_api_engagement_accession_list_states(
    client, service_headers, accessions_by_state, accession, django_assert_max_num_queries
):
    _, accessions = accessions_by_state

    # the state of each result comes from its image and review rows, so without select_related
    # this would grow by two queries per accession.
    with django_assert_max_num_queries(8):
        resp = post_list(client, headers=service_headers)

    assert resp.status_code == 200, resp.json()
    all_results = {result["id"]: result for result in resp.json()["results"]}
    # an accession that didn't come from the engagement platform is never visible here.
    assert all_results.keys() == {accession.pk for accession in accessions.values()}

    for state, engagement_accession in accessions.items():
        external_id = engagement_accession.engagement.external_id
        assert all_results[engagement_accession.pk]["state"] == state
        assert all_results[engagement_accession.pk]["external_id"] == external_id

        resp = post_list(client, {"state": state}, headers=service_headers)
        assert resp.status_code == 200, resp.json()
        # the queryset filter and the state property have to agree, and between them the seven
        # states have to partition the cohort.
        assert [result["id"] for result in resp.json()["results"]] == [engagement_accession.pk]

        resp = post_list(client, {"external_ids": [external_id]}, headers=service_headers)
        assert resp.status_code == 200, resp.json()
        assert [result["id"] for result in resp.json()["results"]] == [engagement_accession.pk]

        resp = client.get(
            reverse("api:engagement_accession_detail", args=[external_id]), headers=service_headers
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["state"] == state

    published = accessions[AccessionState.PUBLISHED]
    assert all_results[published.pk]["isic_id"] == published.image.isic_id
    assert not any(result["isic_id"] for pk, result in all_results.items() if pk != published.pk)

    resp = client.get(
        reverse("api:engagement_accession_detail", args=["no-such-external-id"]),
        headers=service_headers,
    )
    assert resp.status_code == 404, resp.json()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "client_",
    [lf("authenticated_client"), lf("staff_client"), lf("client")],
    ids=["user", "staff", "guest"],
)
@pytest.mark.usefixtures("accessions_by_state")
def test_api_engagement_accession_requires_service_account(client_, engagement_accession):
    """These are for the engagement platform itself, so a user session isn't enough."""
    assert post_list(client_).status_code == 401

    resp = client_.get(
        reverse("api:engagement_accession_detail", args=[engagement_accession.external_id])
    )
    assert resp.status_code == 401
