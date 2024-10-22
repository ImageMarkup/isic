import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
import secrets
import tempfile
from typing import cast
import uuid

from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import connection, transaction
from django.template.loader import render_to_string
from girder_utils.storages import expiring_url
from urllib3.exceptions import ConnectionError, TimeoutError

from isic.core.models.collection import Collection
from isic.core.models.image import Image
from isic.core.search import bulk_add_to_search_index, get_elasticsearch_client, maybe_create_index
from isic.core.serializers import SearchQueryIn
from isic.core.services import staff_image_metadata_csv
from isic.core.services.collection import collection_share
from isic.core.services.collection.image import collection_add_images


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
    soft_time_limit=1200,
    time_limit=1210,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    queue="es-indexing",
)
def sync_elasticsearch_index_task(chunk_size: int = 500):
    es = get_elasticsearch_client()

    tmp_name = secrets.token_hex()
    maybe_create_index(tmp_name)

    bulk_add_to_search_index(
        Image.objects.with_elasticsearch_properties().all(), index=tmp_name, chunk_size=chunk_size
    )

    es.indices.add_block(index=tmp_name, block="write")
    es.indices.delete(index=settings.ISIC_ELASTICSEARCH_INDEX, ignore=[404])
    es.indices.clone(index=tmp_name, target=settings.ISIC_ELASTICSEARCH_INDEX)
    es.indices.delete(index=tmp_name)

    es.indices.refresh(index="_all")


@shared_task(soft_time_limit=1800, time_limit=1810)
def generate_staff_image_list_metadata_csv(user_id: int) -> None:
    user = User.objects.get(pk=user_id, is_staff=True)

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f, transaction.atomic():
        # use repeatable read for the headers and rows to make sure they match
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

        qs = Image.objects.all()
        image_csv = staff_image_metadata_csv(qs=qs)
        writer = csv.DictWriter(f, next(image_csv))
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
