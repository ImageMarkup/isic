from django.urls import reverse
from django.utils.http import urlencode
from faker import Faker
import pytest

fake = Faker()


@pytest.mark.django_db
def test_terms_gate(client, user_factory, settings):
    user = user_factory(profile__accepted_terms=None)
    client.force_login(user)
    gated_url = f"{reverse('core/collection-list')}?{urlencode({'pinned_filter': 'pinned'})}"
    accept_url = reverse("login/accept-terms")

    gated = client.get(gated_url)

    assert gated.status_code == 302
    assert gated.url == f"{accept_url}?{urlencode({'next': gated_url})}"
    assert client.get(reverse("core/terms-of-use")).status_code == 200
    assert client.get(reverse("account_logout")).status_code == 200
    assert client.get(reverse("api:user_me")).status_code == 200

    gate = client.get(gated.url)

    assert gate.status_code == 200
    assert reverse("core/terms-of-use") in gate.content.decode()

    rejected = client.post(accept_url, {"next": gated_url})

    assert rejected.status_code == 200
    assert "You must agree to the Terms of Use" in rejected.content.decode()
    user.profile.refresh_from_db()
    assert user.profile.accepted_terms is None

    accepted = client.post(accept_url, {"next": gated_url, "accept_terms": "on"})

    assert accepted.status_code == 302
    assert accepted.url == gated_url
    user.profile.refresh_from_db()
    assert user.profile.accepted_terms is not None
    assert client.get(gated_url).status_code == 200

    offsite = client.post(accept_url, {"next": fake.url(), "accept_terms": "on"})

    assert offsite.url == settings.LOGIN_REDIRECT_URL
