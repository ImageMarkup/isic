import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from isic.core.services.collection import merge_magic_collections
from isic.ingest.models.accession import Accession
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.contributor import Contributor
from isic.ingest.models.metadata_file import MetadataFile
from isic.ingest.models.metadata_version import MetadataVersion
from isic.ingest.models.zip_upload import ZipUpload

logger = logging.getLogger(__name__)


def create_cohort(  # noqa: PLR0913
    *,
    creator: User,
    contributor: Contributor,
    name: str,
    description: str,
    default_copyright_license: str,
    default_attribution: str,
) -> Cohort:
    with transaction.atomic():
        cohort = Cohort(
            creator=creator,
            contributor=contributor,
            name=name,
            description=description,
            default_copyright_license=default_copyright_license,
            default_attribution=default_attribution,
        )
        # the magic collection is only minted at publish time, and the field isn't blank=True
        cohort.full_clean(exclude=["collection"])
        cohort.save()
        return cohort


def delete_cohort(*, cohort: Cohort) -> None:
    # This check also guarantees the cohort won't point to a collection.
    if cohort.accessions.published().exists():
        raise ValidationError("Cannot delete a cohort with published images.")

    # engagement profiles PROTECT their default cohort
    if cohort.engagement_profiles.exists():
        raise ValidationError(
            "Cannot delete a cohort that engagement users have set as their default."
        )

    with transaction.atomic():
        # metadata versions are set to RESTRICT on delete, so we need to delete them first
        MetadataVersion.objects.filter(accession__in=cohort.accessions.all()).delete()
        cohort.delete()


# TODO: no doi for special collections


def merge_cohorts(*, dest_cohort: Cohort, src_cohort: Cohort) -> None:
    """
    Merge a src_cohort into dest_cohort.

    Note that this method should almost always be used with merge_magic_collections.
    Merging collections or cohorts with relationships to the other would put the system in
    an unexpected state otherwise.
    """
    overlapping_blob_names = (
        Accession.objects.filter(cohort__in=[dest_cohort, src_cohort])
        .values("original_blob_name")
        .annotate(c=Count("cohort", distinct=True))
        .filter(c__gt=1)
    )

    if overlapping_blob_names.exists():
        raise ValidationError(
            f"Found {overlapping_blob_names.count()} conflicting original blob names."
        )

    if (
        src_cohort.lesions.exists()
        or dest_cohort.lesions.exists()
        or src_cohort.patients.exists()
        or dest_cohort.patients.exists()
        or src_cohort.rcm_cases.exists()
        or dest_cohort.rcm_cases.exists()
    ):
        raise ValidationError("Unable to merge cohorts with lesions, patients, or RCM cases.")

    with transaction.atomic():
        # lock cohorts during merge
        # TODO: This is kind of awkward because we need to lock all cohorts but only want to
        # iterate on the other_cohorts.
        list(Cohort.objects.filter(id__in=[dest_cohort.id, src_cohort.id]).select_for_update())

        Accession.objects.filter(cohort=src_cohort).update(cohort=dest_cohort)
        ZipUpload.objects.filter(cohort=src_cohort).update(cohort=dest_cohort)
        MetadataFile.objects.filter(cohort=src_cohort).update(cohort=dest_cohort)

        if src_cohort.collection and dest_cohort.collection:
            merge_magic_collections(
                dest_collection=dest_cohort.collection, src_collection=src_cohort.collection
            )
        elif src_cohort.collection:
            dest_cohort.collection = src_cohort.collection
        # no point in repointing the src collection to the dest collection since it's going away

        # repointing across contributors would leave a profile with a mismatched contributor/cohort
        # pair, so null the default instead.
        same_contributor = src_cohort.contributor_id == dest_cohort.contributor_id
        src_cohort.engagement_profiles.update(
            default_cohort=dest_cohort if same_contributor else None
        )

        src_cohort.delete()
        # dest_cohort has to be saved after the delete to avoid a unique constraint violation
        dest_cohort.save()
