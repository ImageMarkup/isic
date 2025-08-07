from dataclasses import dataclass
import logging

from django.contrib.auth.models import User

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.models.isic_id import IsicId
from isic.login.models import Profile

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    passed: bool
    message: str


def check_public_images_have_sponsored_blob() -> HealthCheckResult:
    public_images_without_sponsored_blob = Image.objects.filter(
        public=True, accession__sponsored_blob=""
    ).count()

    passed = public_images_without_sponsored_blob == 0
    message = (
        "All public images have sponsored blobs"
        if passed
        else f"{public_images_without_sponsored_blob} public images missing sponsored blobs"
    )

    return HealthCheckResult(
        name="public_images_have_sponsored_blob",
        passed=passed,
        message=message,
    )


def check_non_public_images_have_non_sponsored_blob() -> HealthCheckResult:
    non_public_images_with_sponsored_blob = (
        Image.objects.filter(public=False).exclude(accession__sponsored_blob="").count()
    )

    passed = non_public_images_with_sponsored_blob == 0
    message = (
        "All non-public images use non-sponsored blobs"
        if passed
        else f"{non_public_images_with_sponsored_blob} non-public images have sponsored blobs"
    )

    return HealthCheckResult(
        name="non_public_images_have_non_sponsored_blob",
        passed=passed,
        message=message,
    )


def check_no_orphaned_isic_ids() -> HealthCheckResult:
    orphaned_isic_ids = IsicId.objects.filter(image__isnull=True).count()

    passed = orphaned_isic_ids == 0
    message = (
        "No orphaned ISIC IDs found" if passed else f"{orphaned_isic_ids} orphaned ISIC IDs found"
    )

    return HealthCheckResult(
        name="no_orphaned_isic_ids",
        passed=passed,
        message=message,
    )


def check_collections_with_doi_are_locked() -> HealthCheckResult:
    unlocked_collections_with_doi = Collection.objects.filter(
        doi__isnull=False, locked=False
    ).count()

    passed = unlocked_collections_with_doi == 0
    message = (
        "All collections with DOI are locked"
        if passed
        else f"{unlocked_collections_with_doi} collections with DOI are not locked"
    )

    return HealthCheckResult(
        name="collections_with_doi_are_locked",
        passed=passed,
        message=message,
    )


def check_magic_collections_are_locked() -> HealthCheckResult:
    unlocked_magic_collections = Collection.objects.magic().filter(locked=False).count()

    passed = unlocked_magic_collections == 0
    message = (
        "All magic collections are locked"
        if passed
        else f"{unlocked_magic_collections} magic collections are not locked"
    )

    return HealthCheckResult(
        name="magic_collections_are_locked",
        passed=passed,
        message=message,
    )


def check_every_user_has_profile() -> HealthCheckResult:
    users_without_profile = User.objects.exclude(
        id__in=Profile.objects.values_list("user_id", flat=True)
    ).count()

    passed = users_without_profile == 0
    message = (
        "All users have corresponding profiles"
        if passed
        else f"{users_without_profile} users missing profiles"
    )

    return HealthCheckResult(
        name="every_user_has_profile",
        passed=passed,
        message=message,
    )


def check_collection_image_consistency() -> HealthCheckResult:
    private_images_in_public_collections = Image.objects.filter(
        public=False,
        collections__public=True,
    ).count()

    passed = private_images_in_public_collections == 0
    message = (
        "All images in public collections are public"
        if passed
        else f"{private_images_in_public_collections} private images found in public collections"
    )

    return HealthCheckResult(
        name="collection_image_consistency",
        passed=passed,
        message=message,
    )


def check_magic_collections_have_no_doi() -> HealthCheckResult:
    magic_collections_with_doi = Collection.objects.magic().filter(doi__isnull=False).count()

    passed = magic_collections_with_doi == 0
    message = (
        "No magic collections have a DOI"
        if passed
        else f"{magic_collections_with_doi} magic collections have a DOI"
    )

    return HealthCheckResult(
        name="magic_collections_have_no_doi",
        passed=passed,
        message=message,
    )


HEALTH_CHECKS = [
    ("public_images_have_sponsored_blob", check_public_images_have_sponsored_blob),
    ("non_public_images_have_non_sponsored_blob", check_non_public_images_have_non_sponsored_blob),
    # TODO: re-enable in the future after the GirderImage situation is resolved
    # ("no_orphaned_isic_ids", check_no_orphaned_isic_ids),
    ("collections_with_doi_are_locked", check_collections_with_doi_are_locked),
    ("magic_collections_are_locked", check_magic_collections_are_locked),
    ("magic_collections_have_no_doi", check_magic_collections_have_no_doi),
    ("every_user_has_profile", check_every_user_has_profile),
    ("collection_image_consistency", check_collection_image_consistency),
]


def run_all_health_checks() -> list[HealthCheckResult]:
    results = []
    for check_name, check_func in HEALTH_CHECKS:
        result = check_func()
        results.append(result)

        if not result.passed:
            logger.warning("Health check failed: %s - %s", check_name, result.message)

    return results
