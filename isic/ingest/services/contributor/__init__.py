from django.db import transaction

from isic.ingest.models.contributor import Contributor


def merge_contributors(*, dest_contributor: Contributor, src_contributor: Contributor) -> None:
    """Merge a src_contributor into dest_contributor."""
    with transaction.atomic():
        dest_contributor.owners.add(*src_contributor.owners.all())
        src_contributor.cohorts.update(contributor=dest_contributor)
        src_contributor.engagement_profiles.update(default_contributor=dest_contributor)
        src_contributor.email_domains.update(contributor=dest_contributor)
        src_contributor.delete()
