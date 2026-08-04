from django.urls.base import reverse
import pytest
from pytest_lazy_fixtures import lf


@pytest.mark.django_db
def test_engagement_user_list(staff_client, engagement_profile_factory):
    provisioned_profile = engagement_profile_factory(provisioned=True)
    bare_profile = engagement_profile_factory()

    r = staff_client.get(reverse("engagement/user-list"))
    assert r.status_code == 200

    profile_pks = {profile.pk for profile in r.context["profiles"]}
    assert profile_pks == {provisioned_profile.pk, bare_profile.pk}

    content = r.content.decode()
    assert provisioned_profile.default_cohort.name in content
    assert provisioned_profile.default_contributor.institution_name in content
    assert bare_profile.user.email in content


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
