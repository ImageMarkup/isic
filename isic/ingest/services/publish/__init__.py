from collections.abc import Generator
from contextlib import contextmanager
from io import BufferedReader
import logging
from pathlib import Path
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import transaction
from django.db.models import QuerySet
from django.db.models.fields.files import FieldFile
import pyexiv2

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.models.isic_id import IsicId
from isic.core.services.collection import collection_create
from isic.core.services.collection.image import collection_add_images
from isic.core.services.image import image_create
from isic.core.tasks import sync_elasticsearch_indices_task
from isic.core.utils.db import lock_table_for_writes
from isic.core.views.doi import LICENSE_URIS
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


@contextmanager
def embed_iptc_metadata(
    blob: FieldFile, attribution: str, copyright_license: str
) -> Generator[BufferedReader, None, None]:
    # pyexiv2 operates on filenames directly, so we need to write to a temp file
    with tempfile.NamedTemporaryFile() as temp_file:
        shutil.copyfileobj(blob.file, temp_file)
        temp_file.flush()

        with pyexiv2.Image(temp_file.name) as tmp_image:
            tmp_image.modify_iptc(
                {
                    "Iptc.Application2.Copyright": "copyright",
                    "Iptc.Application2.Credit": attribution,
                    "Iptc.Application2.Source": "ISIC Archive",
                }
            )
            tmp_image.modify_xmp(
                {
                    "Xmp.xmpRights.WebStatement": LICENSE_URIS[copyright_license],
                    # necessary to create the "struct" for the licensor URL
                    "Xmp.plus.Licensor": [""],
                    "Xmp.plus.Licensor[1]/plus:LicensorURL": "https://www.isic-archive.com",
                }
            )
        with Path(temp_file.name).open("rb") as f:
            yield f


def unembargo_images(*, qs: QuerySet[Image]) -> None:
    with transaction.atomic():
        for image in qs.select_related("accession").iterator():
            attribution = image.accession.attribution
            copyright_license = image.accession.copyright_license

            with (
                embed_iptc_metadata(
                    image.accession.blob,  # nosem: use-image-blob-where-possible
                    attribution,
                    copyright_license,
                ) as sponsored_blob,
                embed_iptc_metadata(
                    image.accession.thumbnail_256, attribution, copyright_license
                ) as sponsored_thumbnail_256_blob,
            ):
                image.accession.sponsored_blob = File(  # nosem: use-image-blob-where-possible
                    sponsored_blob, name=f"{image.isic_id}.{image.extension}"
                )
                image.accession.sponsored_thumbnail_256_blob = File(
                    sponsored_thumbnail_256_blob, name=f"{image.isic_id}_thumbnail.jpg"
                )
                image.accession.blob = ""  # nosem: use-image-blob-where-possible
                image.accession.thumbnail_256 = ""
                image.accession.save(
                    update_fields=[
                        "sponsored_blob",
                        "blob",
                        "sponsored_thumbnail_256_blob",
                        "thumbnail_256",
                    ]
                )
            image.public = True
            image.save(update_fields=["public"])
