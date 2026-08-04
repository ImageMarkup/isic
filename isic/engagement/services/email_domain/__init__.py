from django.contrib.auth.models import User
from django.db import transaction

from isic.engagement.models import EmailDomainContributor, normalize_email_domain
from isic.ingest.models.contributor import Contributor


def create_email_domain_contributor(
    *, domain: str, contributor: Contributor
) -> EmailDomainContributor:
    with transaction.atomic():
        email_domain_contributor = EmailDomainContributor(domain=domain, contributor=contributor)
        email_domain_contributor.full_clean()
        email_domain_contributor.save()
        return email_domain_contributor


def update_email_domain_contributor(
    *,
    email_domain_contributor: EmailDomainContributor,
    domain: str,
    contributor: Contributor,
) -> EmailDomainContributor:
    with transaction.atomic():
        email_domain_contributor.domain = domain
        email_domain_contributor.contributor = contributor
        email_domain_contributor.full_clean()
        email_domain_contributor.save()
        return email_domain_contributor


def suggest_contributor_for_email(email: str) -> Contributor | None:
    """Return the contributor mapped to an email address' domain, if any."""
    _, at_sign, domain = email.rpartition("@")
    if not at_sign:
        return None

    domain = normalize_email_domain(domain)
    if not domain:
        return None

    email_domain_contributor = (
        EmailDomainContributor.objects.select_related("contributor").filter(domain=domain).first()
    )

    return email_domain_contributor.contributor if email_domain_contributor else None


def suggest_contributor_for_user(user: User) -> Contributor | None:
    """
    Return the contributor suggested by any of a user's email addresses.

    A user can have several email addresses, so every one of them is considered rather than
    only User.email. Unverified addresses are self-asserted and ignored, and the primary
    address wins when more than one maps to a contributor.
    """
    emails = user.emailaddress_set.filter(verified=True).order_by("-primary", "email")  # type: ignore[attr-defined]

    for email in emails.values_list("email", flat=True):
        contributor = suggest_contributor_for_email(email)
        if contributor:
            return contributor

    return None
