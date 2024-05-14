import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count

from isic.core.services.collection import collection_create, collection_merge_magic_collections
from isic.core.services.collection.image import collection_add_images
from isic.core.services.image import image_create
from isic.core.tasks import sync_elasticsearch_index_task
from isic.ingest.models.accession import Accession
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.metadata_file import MetadataFile
from isic.ingest.models.metadata_version import MetadataVersion
from isic.ingest.models.zip_upload import ZipUpload

logger = logging.getLogger(__name__)


def cohort_publish_initialize(*, cohort: Cohort, publisher: User, public: bool) -> None:
    from isic.ingest.tasks import publish_cohort_task

    if not cohort.collection:
        cohort.collection = collection_create(
            creator=publisher,
            name=f"Publish of {cohort.name}",
            description="",
            public=False,  # the collection is always private to avoid leaking cohort names
            locked=True,
        )
        cohort.save(update_fields=["collection"])

    publish_cohort_task.delay(cohort.pk, publisher.pk, public=public)


@transaction.atomic()
def cohort_publish(*, cohort: Cohort, publisher: User, public: bool) -> None:
    for accession in cohort.accessions.publishable().iterator():
        image = image_create(creator=publisher, accession=accession, public=public)
        collection_add_images(collection=cohort.collection, image=image, ignore_lock=True)

    sync_elasticsearch_index_task.delay()


def cohort_delete(*, cohort: Cohort) -> None:
    # This check also guarantees the cohort won't point to a collection.
    if cohort.accessions.published().exists():
        raise ValidationError("Cannot delete a cohort with published images.")

    with transaction.atomic():
        # metadata versions are set to RESTRICT on delete, so we need to delete them first
        MetadataVersion.objects.filter(accession__in=cohort.accessions.all()).delete()
        cohort.delete()


# TODO: no doi for special collections
# speicla collections exist why? keeping track of evolving changing cohorts


def cohort_merge(*, dest_cohort: Cohort, src_cohort: Cohort) -> None:
    """
    Merge a src_cohort into dest_cohort.

    Note that this method should almost always be used with collection_merge_magic_collections.
    Merging collections or cohorts with relationships to the other would put the system in
    an unexpected state otherwise.
    """
    overlapping_blob_names = (
        Cohort.objects.filter(id__in=[dest_cohort.id, src_cohort.id])
        .values("accessions__original_blob_name")
        .annotate(c=Count("id"))
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
            collection_merge_magic_collections(
                dest_collection=dest_cohort.collection, src_collection=src_cohort.collection
            )
        elif src_cohort.collection:
            dest_cohort.collection = src_cohort.collection
        # no point in repointing the src collection to the dest collection since it's going away

        src_cohort.delete()
        # dest_cohort has to be saved after the delete to avoid a unique constraint violation
        dest_cohort.save()
