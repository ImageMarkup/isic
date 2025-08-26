from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile
from typing import cast
import uuid

from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.storage import default_storage, storages
from django.core.mail import send_mail
from django.db import connection, transaction
from django.db.models import Prefetch
from django.template.loader import render_to_string
from oauth2_provider.models import clear_expired as clear_expired_oauth_tokens
import requests
from resonant_utils.storages import expiring_url
from urllib3.exceptions import ConnectionError as Urllib3ConnectionError
from urllib3.exceptions import TimeoutError as Urllib3TimeoutError

from isic.core.health import run_all_health_checks
from isic.core.models.collection import Collection
from isic.core.models.doi import Doi
from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index
from isic.core.serializers import SearchQueryIn
from isic.core.services import staff_image_metadata_csv
from isic.core.services.collection import collection_share
from isic.core.services.collection.image import collection_add_images
from isic.core.services.snapshot import snapshot_images
from isic.core.utils.csv import EscapingDictWriter
from isic.ingest.models.accession import Accession
from isic.ingest.models.lesion import Lesion
from isic.ingest.services.publish import embed_iptc_metadata

logger = get_task_logger(__name__)


@shared_task(soft_time_limit=600, time_limit=610)
def populate_collection_from_search_task(
    collection_pk: int, user_pk: int, search_params: dict
) -> None:
    user = User.objects.get(pk=user_pk)
    collection = Collection.objects.get(pk=collection_pk)

    if "collections" in search_params and not search_params["collections"]:
        del search_params["collections"]

    serializer = SearchQueryIn(**search_params)
    collection_add_images(collection=collection, qs=serializer.to_queryset(user))


@shared_task(soft_time_limit=1800, time_limit=1810)
def share_collection_with_users_task(collection_pk: int, grantor_pk: int, user_pks: list[int]):
    collection = Collection.objects.get(pk=collection_pk)
    grantor = User.objects.get(pk=grantor_pk)
    users = User.objects.filter(pk__in=user_pks)

    # since each instance of collection_share is atomic and idempotent, there's
    # no need to wrap this in a transaction.
    for user in users:
        collection_share(collection=collection, grantor=grantor, grantee=user)


@shared_task(
    soft_time_limit=1800,
    time_limit=1810,
    autoretry_for=(Urllib3ConnectionError, Urllib3TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    queue="es-indexing",
)
def sync_elasticsearch_indices_task():
    bulk_add_to_search_index(
        settings.ISIC_ELASTICSEARCH_IMAGES_INDEX, Image.objects.with_elasticsearch_properties()
    )

    bulk_add_to_search_index(
        settings.ISIC_ELASTICSEARCH_LESIONS_INDEX,
        Lesion.objects
        # only include lesions with images
        .has_images()
        # only look at published accessions
        .prefetch_related(Prefetch("accessions", queryset=Accession.objects.published().order_by()))
        # include elasticsearch properties for the images
        .prefetch_related(
            Prefetch(
                "accessions__image",
                queryset=Image.objects.with_elasticsearch_properties().order_by(),
            )
        )
        .all()
        .order_by(),
    )

    # hasattr is necessary because only the upstream django-redis has
    # the ability to delete patterns.
    if hasattr(cache, "delete_pattern"):
        cache.delete_pattern("get_facets:*")
        cache.delete_pattern("es:*")


@shared_task(soft_time_limit=1800, time_limit=1810)
def generate_staff_image_list_metadata_csv(user_id: int) -> None:
    user = User.objects.get(pk=user_id, is_staff=True)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f, transaction.atomic():
        # use repeatable read for the headers and rows to make sure they match
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

        qs = Image.objects.all()
        image_csv = staff_image_metadata_csv(qs=qs)
        writer = EscapingDictWriter(f, next(image_csv))
        writer.writeheader()

        for metadata_row in image_csv:
            # the generator returns a narrowed type after the first element
            metadata_row = cast(dict[str, str | bool | float], metadata_row)
            writer.writerow(metadata_row)

    current_time = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    csv_filename = f"isic_image_metadata_{current_time}.csv"
    storage_key = f"staff-metadata-csvs/{uuid.uuid4()}/{csv_filename}"

    with Path(f.name).open("rb") as csv_file:
        default_storage.save(storage_key, csv_file)

    signed_url = expiring_url(default_storage, storage_key, timedelta(days=1))

    message = render_to_string(
        "core/email/image_list_metadata_csv_generated.txt", {"csv_url": signed_url}
    )
    send_mail("Metadata CSV Ready", message, settings.DEFAULT_FROM_EMAIL, [user.email])

    Path(f.name).unlink()


@shared_task(soft_time_limit=60 * 60 * 12, time_limit=(60 * 60 * 12) + 60)
def create_doi_bundle_task(doi_id: str) -> None:
    from isic.core.services.collection.doi import collection_create_doi_files

    doi = Doi.objects.get(id=doi_id)

    collection_create_doi_files(doi=doi)


def _fetch_doi_schema_org_dataset(doi_id: str) -> dict:
    r = requests.get(
        f"https://api.datacite.org/dois/{doi_id}",
        headers={"Accept": "application/vnd.schemaorg.ld+json"},
        timeout=(10, 10),
    )
    r.raise_for_status()
    return r.json()


@shared_task(soft_time_limit=20, time_limit=25)
def fetch_doi_schema_org_dataset_task(doi_id: str) -> None:
    doi = Doi.objects.get(id=doi_id)
    doi.schema_org_dataset = _fetch_doi_schema_org_dataset(doi.id)
    doi.schema_org_dataset["isAccessibleForFree"] = True
    doi.save(update_fields=["schema_org_dataset"])


def _fetch_doi_citations(doi_id: str) -> dict[str, str]:
    citations = {}
    for style in settings.ISIC_DATACITE_CITATION_STYLES:
        r = requests.get(
            f"https://api.datacite.org/dois/{doi_id}",
            headers={"Accept": f"text/x-bibliography; style={style}"},
            timeout=(10, 10),
        )
        r.raise_for_status()
        citations[style] = r.text
    return citations


@shared_task(soft_time_limit=120, time_limit=180)
def fetch_doi_citations_task(doi_id: str) -> None:
    doi = Doi.objects.get(id=doi_id)
    doi.citations = _fetch_doi_citations(doi.id)
    doi.save(update_fields=["citations"])


@shared_task(soft_time_limit=12 * 60 * 60, time_limit=12 * 60 * 60 + 60)
def generate_archive_snapshot_task() -> None:
    snapshot_filename, metadata_filename = snapshot_images(qs=Image.objects.public())

    try:
        with Path(snapshot_filename).open("rb") as snapshot_file:
            storages["sponsored"].save("snapshots/ISIC_images.zip", snapshot_file)
    finally:
        Path(snapshot_filename).unlink()
        Path(metadata_filename).unlink()


@shared_task(soft_time_limit=10, time_limit=15)
def prune_expired_oauth_tokens():
    clear_expired_oauth_tokens()


@shared_task(soft_time_limit=90, time_limit=120)
def refresh_materialized_view_collection_counts_task():
    with connection.cursor() as cursor:
        cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY materialized_collection_counts;")


@shared_task(soft_time_limit=180, time_limit=200)
def regenerate_sponsored_blob(image_id: int):
    image = Image.objects.select_related("accession").get(id=image_id)

    accession = image.accession
    attribution = accession.attribution
    copyright_license = accession.copyright_license

    with (
        embed_iptc_metadata(
            accession.sponsored_blob,  # nosem: use-accession-active-blob-where-possible
            attribution,
            copyright_license,
            image.isic_id,
        ) as sponsored_blob,
        embed_iptc_metadata(
            # nosem: use-accession-active-thumbnail-256-where-possible
            accession.sponsored_thumbnail_256_blob,
            attribution,
            copyright_license,
            image.isic_id,
        ) as sponsored_thumbnail_256_blob,
    ):
        s3 = storages["sponsored"]._create_session().client("s3")  # noqa: SLF001
        s3.upload_fileobj(
            sponsored_blob,
            storages["sponsored"].bucket_name,
            f"images/{image.isic_id}.{image.extension}",
        )
        s3.upload_fileobj(
            sponsored_thumbnail_256_blob,
            storages["sponsored"].bucket_name,
            f"thumbnails/{image.isic_id}_thumbnail.jpg",
        )


@shared_task(soft_time_limit=300, time_limit=360)
def run_health_checks_task():
    results = run_all_health_checks()

    for check in results:
        if not check.passed:
            logger.warning(
                "Health check failed: %s - %s",
                check.name,
                check.message,
            )
