from collections.abc import Generator, Iterable
from contextlib import contextmanager
from io import BufferedReader
import logging
from pathlib import Path
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.storage import storages
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
from isic.core.utils.db import lock_table_for_writes
from isic.core.utils.iterators import throttled_iterator
from isic.core.views.doi import LICENSE_URIS
from isic.ingest.models.accession import Accession
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
        publish_request.collections.set(collections)
        # ensure that the magic collection is also added to the publish request
        publish_request.collections.add(cohort.collection)

    publish_cohort_task.delay_on_commit(publish_request.pk)


def cohort_publish(*, publish_request: PublishRequest) -> None:
    from isic.ingest.tasks import publish_accession_task

    additional_collection_ids = list(publish_request.collections.values_list("id", flat=True))

    for accession_pk in throttled_iterator(
        publish_request.accessions.values_list("pk", flat=True).iterator()
    ):
        publish_accession_task.delay_on_commit(
            accession_pk=accession_pk,
            public=publish_request.public,
            publisher_pk=publish_request.creator.pk,
            additional_collection_ids=additional_collection_ids,
        )


def accession_publish(
    *,
    accession: Accession,
    public: bool,
    publisher: User,
    additional_collection_ids: Iterable[int] | None = None,
):
    # wrapping this inside of a transaction ensures that this function can be retried easily
    with lock_table_for_writes(IsicId):
        if accession.attribution == "":
            accession.attribution = accession.cohort.default_attribution
            accession.save(update_fields=["attribution"])

        image_create(
            creator=publisher,
            accession=accession,
            public=False,
        )

        if public:
            unembargo_image(image=accession.image)

        for collection in Collection.objects.filter(id__in=additional_collection_ids):
            collection_add_images(
                collection=collection,
                image=accession.image,
                ignore_lock=True,
            )


@contextmanager
def embed_iptc_metadata(
    blob: FieldFile, attribution: str, copyright_license: str, isic_id: str
) -> Generator[BufferedReader]:
    # pyexiv2 operates on filenames directly, so we need to write to a temp file
    with tempfile.NamedTemporaryFile() as temp_file:
        shutil.copyfileobj(blob.file, temp_file)
        temp_file.flush()

        with pyexiv2.Image(temp_file.name) as tmp_image:
            tmp_image.modify_iptc(
                {
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#credit-line
                    "Iptc.Application2.Credit": attribution,
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#source-supply-chain
                    "Iptc.Application2.Source": "ISIC Archive",
                }
            )
            tmp_image.modify_xmp(
                {
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#title
                    "Xmp.dc.title": isic_id,
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-supplier
                    "Xmp.plus.ImageSupplier": [""],
                    "Xmp.plus.ImageSupplier[1]/plus:ImageSupplierName": "ISIC Archive",
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#image-supplier-image-id
                    "Xmp.plus.ImageSupplierImageID": isic_id,
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#rights-usage-terms
                    "Xmp.xmpRights.UsageTerms": copyright_license,
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#web-statement-of-rights
                    "Xmp.xmpRights.WebStatement": LICENSE_URIS[copyright_license],
                    # necessary to create the "struct" for the licensor data
                    # https://iptc.org/std/photometadata/specification/IPTC-PhotoMetadata#licensor
                    "Xmp.plus.Licensor": [""],
                    "Xmp.plus.Licensor[1]/plus:LicensorURL": "https://www.isic-archive.com",
                    "Xmp.plus.Licensor[1]/plus:LicensorName": "ISIC Archive",
                }
            )
        with Path(temp_file.name).open("rb") as f:
            yield f


def unembargo_image(*, image: Image) -> None:
    storage_keys_to_delete = []

    attribution = image.accession.attribution
    copyright_license = image.accession.copyright_license

    with (
        embed_iptc_metadata(
            image.accession.blob,  # nosem: use-image-blob-where-possible
            attribution,
            copyright_license,
            image.isic_id,
        ) as sponsored_blob,
        embed_iptc_metadata(
            image.accession.thumbnail_256,  # nosem: use-image-thumbnail-256-where-possible
            attribution,
            copyright_license,
            image.isic_id,
        ) as sponsored_thumbnail_256_blob,
    ):
        storage_keys_to_delete.append(
            image.accession.blob.name  # nosem: use-image-blob-where-possible
        )
        storage_keys_to_delete.append(
            image.accession.thumbnail_256.name  # nosem: use-image-thumbnail-256-where-possible
        )

        image.accession.sponsored_blob = File(  # nosem: use-image-blob-where-possible
            sponsored_blob, name=f"{image.isic_id}.{image.extension}"
        )
        # nosem: use-image-thumbnail-256-where-possible
        image.accession.sponsored_thumbnail_256_blob = File(
            sponsored_thumbnail_256_blob,
            name=f"{image.isic_id}_thumbnail.jpg",
        )
        image.accession.blob = ""  # nosem: use-image-blob-where-possible
        image.accession.thumbnail_256 = ""  # nosem: use-image-thumbnail-256-where-possible
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

    def delete_storage_keys():
        for storage_key in storage_keys_to_delete:
            storages["default"].delete(storage_key)

    transaction.on_commit(delete_storage_keys)
