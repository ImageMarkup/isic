from datetime import timezone
import io
import json
import os

from bson.json_util import dumps
from diskcache import Cache
from django.contrib.auth.models import User
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import transaction
import djclick as click
from joblib import Parallel, delayed, parallel_backend
import requests

from isic.core.models import Image
from isic.core.models.segmentation import Segmentation, SegmentationReview
from isic.login.girder import get_girder_db

cache = Cache('.isic-cache', eviction_policy='none', size_limit=1024 * 1024 * 1024 * 1024)


@cache.memoize()
def get_girder_file_bytes(file_id, girder_token):
    original_blob_resp = requests.get(
        f'https://isic-archive.com/api/v1/segmentation/{file_id}/mask',
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


@transaction.atomic
def migrate_segmentation(girder_segmentation):
    mask = None
    try:
        stream, size = get_girder_file_bytes(girder_segmentation['_id'], os.environ['GIRDER_TOKEN'])
    except Exception:
        if girder_segmentation['meta']['flagged'] != 'could not segment':
            print(f'failed to download {girder_segmentation["_id"]}')
    else:
        mask = InMemoryUploadedFile(
            file=stream,
            field_name=None,
            name='segmentation.png',
            content_type='image/png',
            size=size,
            charset=None,
        )

    segmentation, _ = Segmentation.objects.get_or_create(
        girder_id=str(girder_segmentation['_id']),
        defaults={
            'creator': User.objects.get(profile__girder_id=str(girder_segmentation['creatorId'])),
            'image': Image.objects.get(
                accession__girderimage__item_id=str(girder_segmentation['imageId'])
            ),
            'mask': mask,
            'meta': json.loads(dumps(girder_segmentation['meta'])),
        },
    )

    Segmentation.objects.filter(id=segmentation.id).update(
        created=girder_segmentation['created'].replace(tzinfo=timezone.utc),
        modified=girder_segmentation['created'].replace(tzinfo=timezone.utc),
    )

    for review in girder_segmentation.get('reviews', []):
        try:
            user = User.objects.get(profile__girder_id=str(review['userId']))
        except User.DoesNotExist:
            # 1 review uses an admin user that hasn't been migrated, default to Brian
            user = User.objects.get(pk=1)

        segmentation_review, _ = SegmentationReview.objects.get_or_create(
            segmentation_id=segmentation.id,
            creator=user,
            created=review['time'].replace(tzinfo=timezone.utc),
            skill=review['skill'],
            approved=review['approved'],
        )
        SegmentationReview.objects.filter(id=segmentation_review.id).update(
            created=review['time'].replace(tzinfo=timezone.utc),
            modified=review['time'].replace(tzinfo=timezone.utc),
        )


@click.command(help='Migrate girder segmentations to django')
def migrate_girder_segmentations():
    db = get_girder_db()
    with click.progressbar(list(db['segmentation'].find({}))) as girder_segmentations:
        with parallel_backend('threading'):
            Parallel()(
                delayed(migrate_segmentation)(segmentation) for segmentation in girder_segmentations
            )
