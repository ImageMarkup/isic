import logging
from typing import Iterable

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from isic.core.models.image import Image
from isic.core.services.collection import collection_create
from isic.core.services.collection.image import collection_add_images
from isic.core.tasks import sync_elasticsearch_index_task
from isic.ingest.models.cohort import Cohort

logger = logging.getLogger(__name__)


def cohort_publish_initialize(*, cohort: Cohort, publisher: User, public: bool) -> None:
    from isic.ingest.tasks import publish_cohort_task

    if not cohort.collection:
        cohort.collection = collection_create(
            creator=publisher,
            name=f'Publish of {cohort.name}',
            description='',
            public=False,  # the collection is always private to avoid leaking cohort names
            locked=True,
        )
        cohort.save(update_fields=['collection'])

    publish_cohort_task.delay(cohort.pk, publisher.pk, public=public)


def cohort_publish(*, cohort: Cohort, publisher: User, public: bool) -> None:
    for accession in cohort.accessions.publishable().iterator():
        # use get_or_create so the function is idempotent in case of failure
        image, _ = Image.objects.get_or_create(
            creator=publisher,
            accession=accession,
            public=public,
        )
        collection_add_images(collection=cohort.collection, image=image, ignore_lock=True)

    sync_elasticsearch_index_task.delay()


def cohort_delete(*, cohort: Cohort) -> None:
    # This check also guarantees the cohort won't point to a collection.
    if cohort.accessions.published().exists():
        raise ValidationError('Cannot delete a cohort with published images.')

    cohort.delete()


def cohort_merge(*, dest_cohort: Cohort, other_cohorts: Iterable[Cohort]) -> None:
    """
    Merge one or more cohorts into dest_cohort.

    Note that this method should almost always be used with collection_merge. Merging
    collections or cohorts with relationships to the other would put the system in
    an unexpected state otherwise.
    """
    overlapping_blob_names = dest_cohort.accessions.values('original_blob_name')
    for cohort in other_cohorts:
        overlapping_blob_names = overlapping_blob_names.intersection(
            cohort.accessions.values('original_blob_name')
        )

    if overlapping_blob_names.exists():
        raise ValidationError(
            f'Found {overlapping_blob_names.count()} conflicting original blob names.'
        )

    with transaction.atomic():
        for cohort in other_cohorts:
            dest_cohort.accessions.add(*cohort.accessions.all())
            dest_cohort.zip_uploads.add(*cohort.zip_uploads.all())
            dest_cohort.metadata_files.add(*cohort.metadata_files.all())

            if cohort.collection and cohort.collection != dest_cohort.collection:
                logger.warning(f'Abandoning collection {cohort.collection.pk}')

            cohort.delete()
