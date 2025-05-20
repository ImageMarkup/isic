import logging

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.models.isic_id import IsicId
from isic.core.services.collection import collection_create
from isic.core.services.collection.image import collection_add_images
from isic.core.services.image import image_create
from isic.core.tasks import sync_elasticsearch_indices_task
from isic.core.utils.db import lock_table_for_writes
from isic.ingest.models.cohort import Cohort
from isic.ingest.models.publish_request import PublishRequest

logger = logging.getLogger(__name__)


def cohort_publish_initialize(
    *,
    cohort: Cohort,
    publisher: User,
    public: bool,
    collections: QuerySet[Collection] | None = None,
) -> None:
    from isic.ingest.tasks import publish_cohort_task

    collections = collections or Collection.objects.none()

    if not public and collections and collections.filter(public=True).exists():
        raise ValidationError("Can't add private images into a public collection.")

    with transaction.atomic():
        if not cohort.collection:
            cohort.collection = collection_create(
                creator=publisher,
                name=f"Publish of {cohort.name}",
                description="",
                public=False,  # the collection is always private to avoid leaking cohort names
                locked=True,
            )
        cohort.save(update_fields=["collection"])

        publish_request = PublishRequest.objects.create(
            creator=publisher,
            public=public,
        )
        publish_request.accessions.set(cohort.accessions.publishable())
        # ensure that the magic collection is also added to the publish request
        publish_request.collections.set(
            collections.union(Collection.objects.filter(id=cohort.collection.id))
        )

    publish_cohort_task.delay_on_commit(publish_request.pk)


def cohort_publish(*, publish_request: PublishRequest) -> None:
    # this creates a transaction
    with lock_table_for_writes(IsicId), transaction.atomic():
        for accession in publish_request.accessions.iterator():
            if accession.attribution == "":
                accession.attribution = accession.cohort.default_attribution
                accession.save(update_fields=["attribution"])

            image_create(
                creator=publish_request.creator,
                accession=accession,
                public=False,
            )
        if not publish_request.public:
            for collection in publish_request.collections.all():
                collection_add_images(
                    collection=collection,
                    qs=Image.objects.filter(accession__in=publish_request.accessions.all()),
                    ignore_lock=True,
                )

    if publish_request.public:
        with transaction.atomic():
            unembargo_images(
                qs=Image.objects.filter(accession__in=publish_request.accessions.all())
            )

            for collection in publish_request.collections.all():
                collection_add_images(
                    collection=collection,
                    qs=Image.objects.filter(accession__in=publish_request.accessions.all()),
                    ignore_lock=True,
                )

    sync_elasticsearch_indices_task.delay_on_commit()


def unembargo_images(*, qs: QuerySet[Image]) -> None:
    for image in qs.iterator():
        image.public = True
        image.save(update_fields=["public"])
