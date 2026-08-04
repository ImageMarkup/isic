from django.urls import reverse
import pytest
from pytest_lazy_fixtures import lf

from isic.engagement.forms import EmailDomainContributorForm
from isic.engagement.models import EMAIL_DOMAIN_ERROR, EmailDomainContributor
from isic.engagement.services.email_domain import (
    suggest_contributor_for_email,
    suggest_contributor_for_user,
)


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
def test_email_domain_list_permissions(client_, expected_status):
    r = client_.get(reverse("engagement/email-domain-list"))
    assert r.status_code == expected_status


@pytest.mark.django_db
def test_email_domain_list_renders_rows(staff_client, email_domain_contributor_factory):
    r = staff_client.get(reverse("engagement/email-domain-list"))

    assert r.status_code == 200
    assert "No registered email domains" in r.content.decode()

    email_domain_contributor = email_domain_contributor_factory()
    r = staff_client.get(reverse("engagement/email-domain-list"))

    assert r.status_code == 200
    content = r.content.decode()
    assert "No registered email domains" not in content
    assert email_domain_contributor.domain in content
    assert email_domain_contributor.contributor.institution_name in content


@pytest.mark.django_db
def test_email_domain_validation(contributor):
    # only surrounding whitespace and case are normalized away
    normalized = {
        "  MSKCC.org ": "mskcc.org",
        "mepcoeng.ac.in": "mepcoeng.ac.in",
        "Gallery.Sub.MepcoEng.ac.in": "gallery.sub.mepcoeng.ac.in",
    }
    for posted_domain, expected_domain in normalized.items():
        form = EmailDomainContributorForm(
            data={"domain": posted_domain, "contributor": contributor.pk}
        )
        assert form.is_valid(), form.errors
        assert form.instance.domain == expected_domain

    for domain in ["not a domain", "mskcc", "mskcc.org.", "someone@mskcc.org", "@mskcc.org"]:
        form = EmailDomainContributorForm(data={"domain": domain, "contributor": contributor.pk})
        assert not form.is_valid(), domain
        assert EMAIL_DOMAIN_ERROR in form.errors["domain"]


@pytest.mark.django_db
def test_email_domain_create(staff_client, contributor):
    r = staff_client.post(
        reverse("engagement/email-domain-list"),
        data={"domain": "  MSKCC.org ", "contributor": contributor.pk},
    )

    assert r.status_code == 302
    assert r.url == reverse("engagement/email-domain-list")
    email_domain = EmailDomainContributor.objects.get()
    assert email_domain.domain == "mskcc.org"
    assert email_domain.contributor == contributor

    # a differently cased duplicate is caught as a form error, not an IntegrityError
    r = staff_client.post(
        reverse("engagement/email-domain-list"),
        data={"domain": "MSKCC.ORG", "contributor": contributor.pk},
    )

    assert r.status_code == 200
    assert "already exists" in r.content.decode()

    r = staff_client.post(
        reverse("engagement/email-domain-list"),
        data={"domain": "not a domain", "contributor": contributor.pk},
    )

    assert r.status_code == 200
    assert EMAIL_DOMAIN_ERROR in r.content.decode()
    assert EmailDomainContributor.objects.count() == 1


@pytest.mark.django_db
def test_email_domain_edit(staff_client, email_domain_contributor, contributor_factory):
    new_contributor = contributor_factory()
    url = reverse("engagement/email-domain-edit", args=[email_domain_contributor.pk])

    assert staff_client.get(url).status_code == 200

    r = staff_client.post(url, data={"domain": "example.org", "contributor": new_contributor.pk})

    assert r.status_code == 302
    assert r.url == reverse("engagement/email-domain-list")
    email_domain_contributor.refresh_from_db()
    assert email_domain_contributor.domain == "example.org"
    assert email_domain_contributor.contributor == new_contributor


@pytest.mark.django_db
def test_email_domain_delete(staff_client, email_domain_contributor):
    url = reverse("engagement/email-domain-delete", args=[email_domain_contributor.pk])

    # deletion is POST only
    assert staff_client.get(url).status_code == 405
    assert EmailDomainContributor.objects.filter(pk=email_domain_contributor.pk).exists()

    r = staff_client.post(url)

    assert r.status_code == 302
    assert r.url == reverse("engagement/email-domain-list")
    assert not EmailDomainContributor.objects.filter(pk=email_domain_contributor.pk).exists()


@pytest.mark.django_db
def test_suggest_contributor_for_email(email_domain_contributor):
    domain = email_domain_contributor.domain
    contributor = email_domain_contributor.contributor

    assert suggest_contributor_for_email(f"someone@{domain}") == contributor
    assert suggest_contributor_for_email(f"Someone+Tagged@{domain.upper()}") == contributor
    assert suggest_contributor_for_email(f"someone@other-{domain}") is None
    assert suggest_contributor_for_email("") is None
    assert suggest_contributor_for_email("someone@") is None
    # a bare domain isn't an email address
    assert suggest_contributor_for_email(domain) is None


@pytest.mark.django_db
def test_suggest_contributor_for_user(
    user, email_address_factory, email_domain_contributor_factory
):
    # the address the user was created with maps to nothing
    assert suggest_contributor_for_user(user) is None

    unverified_match = email_domain_contributor_factory()
    email_address_factory(
        user=user,
        email=f"someone@{unverified_match.domain}",
        verified=False,
        primary=False,
    )
    # unverified addresses are self-asserted, so they don't produce a suggestion
    assert suggest_contributor_for_user(user) is None

    secondary_match = email_domain_contributor_factory()
    email_address_factory(
        user=user,
        email=f"someone@{secondary_match.domain}",
        verified=True,
        primary=False,
    )
    # every verified address is considered, not just the primary one
    assert suggest_contributor_for_user(user) == secondary_match.contributor

    primary_match = email_domain_contributor_factory()
    user.emailaddress_set.filter(primary=True).update(email=f"someone@{primary_match.domain}")
    # the primary address wins when several addresses map to different contributors
    assert suggest_contributor_for_user(user) == primary_match.contributor
