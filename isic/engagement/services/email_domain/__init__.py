from collections.abc import Iterable

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import CharField, Func, OuterRef, Subquery
from django.db.models.functions import Lower, Trim

from isic.engagement.models import EmailDomainContributor
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor


class EmailDomain(Func):
    """The portion of an email address after the last @, or NULL when there is no @."""

    function = "substring"
    template = "%(function)s(%(expressions)s FROM '@([^@]*)$')"
    output_field = CharField()


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


def suggest_contributor_for_users(users: Iterable[User]) -> dict[int, Contributor]:
    """
    Return the contributor suggested by each user's email addresses, keyed by user id.

    A user can have several email addresses, so every one of them is considered rather than
    only User.email. Unverified addresses are self-asserted and ignored, and the primary
    address wins when more than one maps to a contributor. Users without a suggestion are
    absent from the result.
    """
    contributor_ids_by_user_id = dict(
        EmailAddress.objects.filter(user__in=list(users), verified=True)
        .annotate(email_domain=Lower(Trim(EmailDomain("email"))))
        # narrowing to addresses that actually map is what makes DISTINCT ON correct. without
        # it the highest priority verified address wins whether or not it maps to anything,
        # so a user whose primary address is unmapped would get no suggestion at all even
        # though one of their other addresses maps.
        .filter(email_domain__in=EmailDomainContributor.objects.values("domain"))
        .annotate(
            suggested_contributor_id=Subquery(
                EmailDomainContributor.objects.filter(domain=OuterRef("email_domain")).values(
                    "contributor"
                )[:1]
            )
        )
        # DISTINCT ON requires the ordering to lead with the distinct field, which happens to
        # be the shape this wants anyway: the primary address wins, then the alphabetically
        # first.
        .order_by("user_id", "-primary", "email")
        .distinct("user_id")
        .values_list("user_id", "suggested_contributor_id")
    )

    contributors = Contributor.objects.in_bulk(set(contributor_ids_by_user_id.values()))

    return {
        user_id: contributors[contributor_id]
        for user_id, contributor_id in contributor_ids_by_user_id.items()
    }


def suggest_cohort_for_contributor(contributor: Contributor) -> Cohort | None:
    """
    Return the cohort a contributor's uploads should land in, if it's unambiguous.

    Only a contributor with exactly one cohort produces a suggestion. Picking one of several
    would be a guess, and the cohort determines the license every image is submitted under.
    """
    cohorts = contributor.cohorts.all()[:2]
    return cohorts[0] if len(cohorts) == 1 else None
