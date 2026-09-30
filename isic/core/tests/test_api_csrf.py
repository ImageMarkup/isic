from datetime import timedelta
from urllib.parse import urlparse

from django.test.client import Client
from django.urls import reverse
from django.utils import timezone
from oauth2_provider.models import get_access_token_model
import pytest

from isic.core.models import Collection
from isic.core.models.base import IsicOAuthApplication


@pytest.fixture
def user(user_factory):
    return user_factory(profile__accepted_terms=None)


@pytest.fixture
def csrf_client(user):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


@pytest.fixture
def csrf_bearer_client(user, user_factory, faker):
    application = IsicOAuthApplication.objects.create(
        name=faker.company(),
        redirect_uris="http://localhost",
        user=user_factory(),
        client_type=IsicOAuthApplication.CLIENT_CONFIDENTIAL,
        authorization_grant_type=IsicOAuthApplication.GRANT_AUTHORIZATION_CODE,
    )
    token = get_access_token_model().objects.create(
        user=user,
        token=faker.pystr(min_chars=30, max_chars=30),
        application=application,
        expires=timezone.now() + timedelta(hours=1),
    )
    return Client(enforce_csrf_checks=True, headers={"Authorization": f"Bearer {token.token}"})


def csrf_token(client) -> str:
    # any page rendering a csrf token sets the cookie, just as a browser would receive it.
    client.get(reverse("login/accept-terms"))
    return client.cookies["csrftoken"].value


@pytest.mark.django_db
def test_session_requests_require_csrf_token(csrf_client, user, collection_factory, faker):
    collection = collection_factory(creator=user, public=False, locked=False)

    for method, url, body in [
        ("put", reverse("api:user_accept_terms"), {}),
        ("delete", reverse("api:collection_detail", args=[collection.pk]), ""),
        (
            "post",
            reverse("api:collection_create_from_isic_ids"),
            {"name": faker.sentence(), "isic_ids": ["ISIC_0000000"]},
        ),
    ]:
        r = getattr(csrf_client, method)(url, body, content_type="application/json")
        assert r.status_code == 403, (method, url)
        assert r.json()["detail"].startswith("CSRF Failed"), (method, url)

    user.profile.refresh_from_db()
    assert user.profile.accepted_terms is None
    assert Collection.objects.filter(pk=collection.pk).exists()

    token = csrf_token(csrf_client)
    r = csrf_client.put(
        reverse("api:user_accept_terms"),
        {},
        content_type="application/json",
        headers={"X-CSRFToken": token},
    )
    assert r.status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.accepted_terms is not None

    r = csrf_client.delete(
        reverse("api:collection_detail", args=[collection.pk]), headers={"X-CSRFToken": token}
    )
    assert r.status_code == 204


@pytest.mark.django_db
def test_non_json_bodies_are_rejected(csrf_client, csrf_bearer_client, faker):
    # a cross site html form can send these without a preflight
    for client in [csrf_client, csrf_bearer_client]:
        for content_type, body in [
            ("text/plain", f'{{"name": "{faker.word()}", "isic_ids": ["ISIC_0000000"]}}'),
            ("application/x-www-form-urlencoded", f"name={faker.word()}&isic_ids=ISIC_0000000"),
            ("multipart/form-data; boundary=BoUnDaRyStRiNg", "--BoUnDaRyStRiNg--\r\n"),
        ]:
            r = client.post(
                reverse("api:collection_create_from_isic_ids"), body, content_type=content_type
            )
            assert r.status_code == 415, content_type

    assert not Collection.objects.exists()


@pytest.mark.django_db
def test_bearer_requests_are_exempt_from_csrf(csrf_bearer_client, user):
    r = csrf_bearer_client.put(
        reverse("api:user_accept_terms"), {}, content_type="application/json"
    )
    assert r.status_code == 200
    user.profile.refresh_from_db()
    assert user.profile.accepted_terms is not None


@pytest.mark.django_db
def test_anonymous_requests_are_exempt_from_csrf(settings, faker):
    settings.ISIC_ZIP_DOWNLOAD_SERVICE_URL = urlparse(faker.url())
    client = Client(enforce_csrf_checks=True)

    r = client.post(reverse("api:zip_download_url"), {}, content_type="application/json")
    assert r.status_code == 200
