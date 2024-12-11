from django.db import transaction

from isic.ingest.models.contributor import Contributor


def contributor_merge(*, dest_contributor: Contributor, src_contributor: Contributor) -> None:
    """Merge a src_contributor into dest_contributor."""
    with transaction.atomic():
        dest_contributor.owners.add(*src_contributor.owners.all())
        src_contributor.cohorts.update(contributor=dest_contributor)
        src_contributor.delete()
