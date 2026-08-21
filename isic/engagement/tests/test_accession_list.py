from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.ingest.models.accession import AccessionState


@pytest.mark.django_db
def test_engagement_accession_list(staff_client, engagement_accessions_by_state, accession):
    # the filter defaults on, so only the accessions that haven't reached a terminal state are
    # listed. an accession that didn't come from the engagement platform is never listed at all.
    r = staff_client.get(reverse("engagement/accession-list"))
    assert r.status_code == 200
    assert {listed.pk for listed in r.context["page"]} == {
        engagement_accessions_by_state[state].pk for state in AccessionState if not state.terminal
    }

    r = staff_client.get(reverse("engagement/accession-list"), {"only_in_flight": "0"})
    assert r.status_code == 200
    assert {listed.pk for listed in r.context["page"]} == {
        listed.pk for listed in engagement_accessions_by_state.values()
    }
    assert accession.pk not in {listed.pk for listed in r.context["page"]}


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
def test_engagement_accession_list_permissions(client_, expected_status):
    r = client_.get(reverse("engagement/accession-list"))
    assert r.status_code == expected_status
