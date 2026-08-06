from django.contrib.auth.models import User
from django.db import transaction

from isic.ingest.models.contributor import Contributor


def create_contributor(  # noqa: PLR0913
    *,
    creator: User,
    institution_name: str,
    legal_contact_info: str,
    institution_url: str = "",
    default_copyright_license: str = "",
    default_attribution: str = "",
) -> Contributor:
    with transaction.atomic():
        contributor = Contributor(
            creator=creator,
            institution_name=institution_name,
            legal_contact_info=legal_contact_info,
            institution_url=institution_url,
            default_copyright_license=default_copyright_license,
            default_attribution=default_attribution,
        )
        contributor.full_clean()
        contributor.save()
        contributor.owners.add(creator)
        return contributor


def merge_contributors(*, dest_contributor: Contributor, src_contributor: Contributor) -> None:
    """Merge a src_contributor into dest_contributor."""
    with transaction.atomic():
        dest_contributor.owners.add(*src_contributor.owners.all())
        src_contributor.cohorts.update(contributor=dest_contributor)
        src_contributor.engagement_profiles.update(default_contributor=dest_contributor)
        src_contributor.email_domains.update(contributor=dest_contributor)
        src_contributor.delete()
