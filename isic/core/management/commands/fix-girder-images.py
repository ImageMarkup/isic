from datetime import datetime, timezone
import io
import os

from diskcache import Cache
from django.db import transaction
import djclick as click
from joblib import Parallel, delayed, parallel_backend
import requests

from isic.core.models.girder_image import GirderImage
from isic.core.models.image import Image
from isic.ingest.models import Accession
from isic.ingest.models.accession import AccessionStatus
from isic.ingest.models.check_log import CheckLog
from isic.ingest.models.cohort import Cohort
from isic.ingest.tasks import process_accession_task, publish_accession_task
from isic.ingest.utils.zip import Blob
from isic.ingest.validators import MetadataRow
from isic.login.models import Profile

cache = Cache('.isic-cache', eviction_policy='none', size_limit=1024 * 1024 * 1024 * 1024)


@cache.memoize()
def get_girder_file_bytes(file_id, girder_token):
    original_blob_resp = requests.get(
        f'https://isic-archive.com/api/v1/file/{file_id}/download',
        headers={'girder-token': girder_token},
        stream=True,
    )
    original_blob_resp.raise_for_status()

    original_blob_stream = io.BytesIO()
    for chunk in original_blob_resp.iter_content(chunk_size=1024 * 1024 * 5):
        original_blob_stream.write(chunk)
    size = original_blob_stream.tell()
    original_blob_stream.seek(0)

    return original_blob_stream, size


def migrate_reviewed(accession, item):
    item['created'] = datetime.utcfromtimestamp(item['created']['$date'] / 1000.0).replace(
        tzinfo=timezone.utc
    )
    item['updated'] = datetime.utcfromtimestamp(item['updated']['$date'] / 1000.0).replace(
        tzinfo=timezone.utc
    )

    if accession.quality_check is not None and accession.phi_check is not None:
        return

    if item['meta'].get('reviewed'):
        review = item['meta']['reviewed']
        review['time'] = datetime.utcfromtimestamp(review['time']['$date'] / 1000.0).replace(
            tzinfo=timezone.utc
        )
        assert review['accepted']
        with transaction.atomic():
            accession.phi_check = True
            accession.quality_check = True
            accession.save(update_fields=['phi_check', 'quality_check'])

            reviewer = Profile.objects.get(girder_id=review['userId']['$oid']).user
            assert reviewer

            for field in ['phi_check', 'quality_check']:
                log = accession.checklogs.create(
                    creator=reviewer, change_field=field, change_to=True
                )
                CheckLog.objects.filter(pk=log.pk).update(
                    created=review['time'].replace(tzinfo=timezone.utc),
                    modified=review['time'].replace(tzinfo=timezone.utc),
                )


def migrate_unstructured_and_exif(accession: Accession, item):
    item['meta'].setdefault('unstructuredExif', {})

    unstructured_keys = set(item['meta']['unstructured'].keys())
    unstructured_exif_keys = set(item['meta']['unstructuredExif'])

    overlap = unstructured_keys.intersection(unstructured_exif_keys)
    assert overlap == set()

    total_meta = {**item['meta']['unstructured'], **item['meta']['unstructuredExif']}

    accession.unstructured_metadata = total_meta
    accession.save(update_fields=['unstructured_metadata'])


def migrate_clinical_metadata(accession: Accession, item):
    # VSHR
    if accession.cohort.id == 180:
        item['meta']['clinical'].setdefault('benign_malignant', 'benign')

    if item['meta'].get('acquisition', {}).get('dermoscopic_type'):
        item['meta']['clinical']['dermoscopic_type'] = item['meta']['acquisition'][
            'dermoscopic_type'
        ]
    if item['meta'].get('acquisition', {}).get('image_type'):
        item['meta']['clinical']['image_type'] = item['meta']['acquisition']['image_type']

    if 'age_approx' in item['meta']['clinical']:
        del item['meta']['clinical']['age_approx']
    if item['privateMeta'].get('age'):
        item['meta']['clinical']['age'] = item['privateMeta']['age']

    try:
        m = MetadataRow.parse_obj(item['meta']['clinical'])
        accession.metadata = m.dict(exclude_unset=True, exclude_none=True, exclude={'unstructured'})
    except Exception as e:
        print(accession.cohort.name, e)
    else:
        accession.save(update_fields=['metadata'])


def migrate_metadata(accession: Accession, item: dict):
    migrate_reviewed(accession, item)
    migrate_unstructured_and_exif(accession, item)
    migrate_clinical_metadata(accession, item)


def _fix_girder_image(girder_image, girder_token):
    # thumbs.db
    if girder_image.isic_id == 'ISIC_0053452':
        return

    original_blob_stream, size = get_girder_file_bytes(girder_image.file_id, girder_token)

    with transaction.atomic():
        a = Accession.from_blob(
            Blob(
                girder_image.original_filename,
                original_blob_stream,
                size,
            )
        )
        a.girder_id = girder_image.item_id
        a.cohort = Cohort.objects.get(girder_id=girder_image.dataset_id)
        a.status = AccessionStatus.CREATED
        a.save()

        Accession.objects.filter(pk=a.pk).update(
            created=datetime.utcfromtimestamp(
                girder_image.raw['created']['$date'] / 1000.0
            ).replace(tzinfo=timezone.utc),
            modified=datetime.utcfromtimestamp(
                girder_image.raw['updated']['$date'] / 1000.0
            ).replace(tzinfo=timezone.utc),
        )

        process_accession_task.delay(a.pk)

        girder_image.accession = a
        girder_image.save()

        migrate_metadata(a, girder_image.raw)

        girder_image.refresh_from_db()
        # publish image
        # should it be public?
        public_cohort_values = set(
            Image.objects.values_list('public', flat=True).filter(
                accession__cohort__girder_id=girder_image.dataset_id
            )
        )
        assert len(public_cohort_values) == 1
        publish_accession_task(girder_image.accession.pk, public=public_cohort_values.pop())


@click.command(help='Fix the GirderImage table so duplicates have duplicate accessions')
def fix_girder_images():
    girder_token = os.environ['GIRDER_TOKEN']

    with click.progressbar(
        GirderImage.objects.select_related('isic').filter(accession=None).all()
    ) as items:
        with parallel_backend('threading'):
            Parallel()(
                delayed(_fix_girder_image)(girder_image, girder_token) for girder_image in items
            )
