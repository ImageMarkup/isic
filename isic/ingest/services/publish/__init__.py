import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction

from isic.core.models.collection import Collection
from isic.core.models.isic_id import IsicId
from isic.core.services.collection import collection_create
from isic.core.services.collection.image import collection_add_images
from isic.core.services.image import image_create
from isic.core.tasks import sync_elasticsearch_indices_task
from isic.core.utils.db import lock_table_for_writes
from isic.ingest.models.cohort import Cohort

logger = logging.getLogger(__name__)


def cohort_publish_initialize(
    *, cohort: Cohort, publisher: User, public: bool, collection_ids: list[int] | None = None
) -> None:
    from isic.ingest.tasks import publish_cohort_task

    if (
        not public
        and collection_ids
        and Collection.objects.filter(pk__in=collection_ids, public=True).exists()
    ):
        raise ValidationError("Can't add private images into a public collection.")

    if not cohort.collection:
        cohort.collection = collection_create(
            creator=publisher,
            name=f"Publish of {cohort.name}",
            description="",
            public=False,  # the collection is always private to avoid leaking cohort names
            locked=True,
        )
        cohort.save(update_fields=["collection"])

    publish_cohort_task.delay_on_commit(
        cohort.pk, publisher.pk, public=public, collection_ids=collection_ids
    )


def cohort_publish(
    *, cohort: Cohort, publisher: User, public: bool, collection_ids: list[int] | None = None
) -> None:
    additional_collections = (
        Collection.objects.filter(pk__in=collection_ids) if collection_ids else []
    )

    # this creates a transaction
    with lock_table_for_writes(IsicId), transaction.atomic():
        for accession in cohort.accessions.publishable().iterator():
            if accession.attribution == "":
                accession.attribution = accession.cohort.default_attribution
                accession.save(update_fields=["attribution"])

            image = image_create(creator=publisher, accession=accession, public=public)
            collection_add_images(collection=cohort.collection, image=image, ignore_lock=True)

            for additional_collection in additional_collections:
                collection_add_images(
                    collection=additional_collection, image=image, ignore_lock=True
                )

    sync_elasticsearch_indices_task.delay_on_commit()
