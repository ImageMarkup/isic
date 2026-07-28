from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.constraints import CheckConstraint
from django.db.models.query_utils import Q
from django.dispatch import receiver
from oauth2_provider.signals import app_authorized

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
        Contributor, on_delete=models.PROTECT, null=True, related_name="engagement_profiles"
    )
    default_cohort = models.ForeignKey(
        Cohort, on_delete=models.PROTECT, null=True, related_name="engagement_profiles"
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


@receiver(app_authorized)
def create_engagement_profile(sender, request, token, **kwargs):
    """Mark a user as an engagement user on their first engagement platform token grant."""
    if not settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID:
        return

    if token.application.client_id != settings.ISIC_ENGAGEMENT_OAUTH_CLIENT_ID:
        return

    EngagementProfile.objects.get_or_create(user=token.user)
