from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Q

from isic.ingest.models.accession import Accession
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


@dataclass(frozen=True)
class MergeImpactUser:
    id: int
    name: str
    email: str
    has_engagement_profile: bool


@dataclass(frozen=True)
class MergeImpactContributor:
    id: int
    institution_name: str
    accession_count: int
    published_image_count: int


@dataclass(frozen=True)
class ContributorMergeImpact:
    dest_contributor: MergeImpactContributor
    src_contributor: MergeImpactContributor
    # owners of the source that aren't owners of the destination yet, they gain access to
    # everything the destination already has.
    users_gaining_access_to_dest: list[MergeImpactUser]
    # owners of the destination that aren't owners of the source, they gain access to the
    # source's data once it moves under the destination.
    users_gaining_access_to_src: list[MergeImpactUser]
    engagement_profiles_repointed: list[MergeImpactUser]


def _merge_impact_contributor(contributor: Contributor) -> MergeImpactContributor:
    counts = Accession.objects.filter(cohort__contributor=contributor).aggregate(
        accession_count=Count("id"),
        # mirrors AccessionQuerySet.published, an accession is published once it has an image
        published_image_count=Count("id", filter=Q(image__isnull=False)),
    )
    return MergeImpactContributor(
        id=contributor.pk,
        institution_name=contributor.institution_name,
        accession_count=counts["accession_count"],
        published_image_count=counts["published_image_count"],
    )


def _merge_impact_user(user: User, *, has_engagement_profile: bool) -> MergeImpactUser:
    return MergeImpactUser(
        id=user.pk,
        name=user.get_full_name() or user.email,
        email=user.email,
        has_engagement_profile=has_engagement_profile,
    )


def compute_contributor_merge_impact(
    *, dest_contributor: Contributor, src_contributor: Contributor
) -> ContributorMergeImpact:
    """
    Describe who gains access to what by merging src_contributor into dest_contributor.

    Access is granted exclusively by Contributor.owners, so merging exposes each contributor's
    data to the other's owners. Note that the two contributors must be different.
    """
    dest_owners = list(dest_contributor.owners.order_by("email"))
    src_owners = list(src_contributor.owners.order_by("email"))

    engagement_user_ids = set(
        User.objects.filter(
            pk__in=[user.pk for user in dest_owners + src_owners],
            engagement_profile__isnull=False,
        ).values_list("pk", flat=True)
    )

    def users_gaining_access(
        owners: list[User], existing_owners: list[User]
    ) -> list[MergeImpactUser]:
        existing_owner_ids = {user.pk for user in existing_owners}
        return [
            _merge_impact_user(user, has_engagement_profile=user.pk in engagement_user_ids)
            for user in owners
            if user.pk not in existing_owner_ids
        ]

    return ContributorMergeImpact(
        dest_contributor=_merge_impact_contributor(dest_contributor),
        src_contributor=_merge_impact_contributor(src_contributor),
        users_gaining_access_to_dest=users_gaining_access(src_owners, dest_owners),
        users_gaining_access_to_src=users_gaining_access(dest_owners, src_owners),
        engagement_profiles_repointed=[
            _merge_impact_user(profile.user, has_engagement_profile=True)
            for profile in src_contributor.engagement_profiles.select_related("user").order_by(
                "user__email"
            )
        ],
    )


def merge_contributors(*, dest_contributor: Contributor, src_contributor: Contributor) -> None:
    """Merge a src_contributor into dest_contributor."""
    with transaction.atomic():
        dest_contributor.owners.add(*src_contributor.owners.all())
        src_contributor.cohorts.update(contributor=dest_contributor)
        src_contributor.engagement_profiles.update(default_contributor=dest_contributor)
        src_contributor.email_domains.update(contributor=dest_contributor)
        src_contributor.delete()
