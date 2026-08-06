from django.core.exceptions import ValidationError
from django.db import transaction

from isic.engagement.models import EngagementProfile
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor


def assign_engagement_defaults(
    *,
    engagement_profile: EngagementProfile,
    contributor: Contributor,
    cohort: Cohort | None = None,
) -> None:
    """
    Set an engagement user's defaults and give them access to them.

    Recording the defaults isn't enough on its own. Uploading into a cohort requires ownership of
    its contributor (see CohortPermissions.add_accession), so assignment grants that too, which
    also reveals the contributor's existing cohorts and accessions to the user.
    """
    if cohort is not None and cohort.contributor_id != contributor.pk:
        raise ValidationError(
            f"{cohort.name} belongs to a different contributor than {contributor.institution_name}."
        )

    with transaction.atomic():
        engagement_profile.default_contributor = contributor
        engagement_profile.default_cohort = cohort
        engagement_profile.full_clean()
        engagement_profile.save()

        contributor.owners.add(engagement_profile.user)
