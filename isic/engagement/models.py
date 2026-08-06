from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.query_utils import Q
from django.dispatch import receiver
from oauth2_provider.signals import app_authorized

from isic.core.models.base import CreationSortedTimeStampedModel
from isic.ingest.models import Cohort, Contributor


class EngagementProfile(models.Model):
    """
    The engagement platform specific defaults for a user.

    The existence of a row is the signal that a user is an engagement platform user. The
    defaults are null, and are deliberately separate from isic.login.Profile, which holds global
    user properties.
    """

    created = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="engagement_profile")
    # the contributor is stored separately rather than derived from default_cohort.contributor
    # so it can be suggested automatically, which isn't something that can be done for cohorts.
    # deriving it would also mean a user needs a cohort before they have a contributor, which
    # pushes towards a single catch-all "engagement platform" cohort.
    default_contributor = models.ForeignKey(
        Contributor,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="engagement_profiles",
    )
    default_cohort = models.ForeignKey(
        Cohort, on_delete=models.PROTECT, null=True, blank=True, related_name="engagement_profiles"
    )

    class Meta:
        constraints = [
            # a default cohort implies a default contributor, since default_contributor is always
            # default_cohort.contributor. the reverse isn't true, a user can have a contributor
            # before they have a cohort. the cross table half of the invariant is covered by the
            # engagement_profile_defaults_consistent health check.
            CheckConstraint(
                name="engagement_profile_cohort_implies_contributor",
                condition=Q(default_cohort__isnull=True) | Q(default_contributor__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        return self.user.username


# the hyphen must stay escaped. the form hands this to the browser as an HTML5 pattern, which
# is compiled as a regex with the "v" flag, and an unescaped trailing "-" in a character class
# is a syntax error there. browsers skip pattern validation silently when it doesn't compile,
# so unescaping it disables client side validation without any visible sign.
_DOMAIN_LABEL = r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
# either case is accepted because domains are only lowercased during cleaning, after the
# validator has already run.
EMAIL_DOMAIN_PATTERN = rf"{_DOMAIN_LABEL}(\.{_DOMAIN_LABEL})+"

EMAIL_DOMAIN_ERROR = "Enter a valid domain, e.g. mskcc.org."


def normalize_email_domain(domain: str) -> str:
    """Normalize a domain, tolerating surrounding whitespace and mixed case."""
    return domain.strip().lower()


class EmailDomainContributor(CreationSortedTimeStampedModel):
    """Maps an email domain to the contributor its users most likely belong to."""

    class Meta(CreationSortedTimeStampedModel.Meta):
        ordering = ["domain"]

    domain = models.CharField(
        max_length=255,
        unique=True,
        validators=[RegexValidator(regex=rf"^{EMAIL_DOMAIN_PATTERN}$", message=EMAIL_DOMAIN_ERROR)],
        help_text="The email domain, e.g. mskcc.org.",
    )
    contributor = models.ForeignKey(
        Contributor, on_delete=models.PROTECT, related_name="email_domains"
    )

    def clean(self) -> None:
        # normalizing here rather than in the form means every writer gets it, and it runs
        # before validate_unique, so a differently cased duplicate is a friendly form error.
        super().clean()
        self.domain = normalize_email_domain(self.domain)

    def __str__(self) -> str:
        return self.domain


@receiver(app_authorized)
def create_engagement_profile(sender, request, token, **kwargs):
    """Mark a user as an engagement user on their first engagement platform token grant."""
    if not settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID:
        return

    if token.application.client_id != settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID:
        return

    EngagementProfile.objects.get_or_create(user=token.user)
