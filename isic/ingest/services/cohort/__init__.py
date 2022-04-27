from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from isic.core.models.image import Image
from isic.core.services.collection import collection_create
from isic.core.services.collection.image import collection_add_images
from isic.core.tasks import sync_elasticsearch_index_task
from isic.ingest.models.cohort import Cohort


def cohort_publish_initialize(*, cohort: Cohort, publisher: User, public: bool) -> None:
    from isic.ingest.tasks import publish_cohort_task

    if not cohort.collection:
        cohort.collection = collection_create(
            creator=publisher,
            name=f'Publish of {cohort.name}',
            description='',
            public=False,  # the collection is always private to avoid leaking cohort names
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
    if cohort.accessions.published().exists():
        raise ValidationError('Cannot delete a cohort with published images.')

    cohort.delete()
