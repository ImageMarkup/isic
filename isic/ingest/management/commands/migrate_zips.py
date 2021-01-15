import datetime

import djclick as click
import requests
from django.core.files import File
from django.core.files.uploadedfile import UploadedFile

from isic.login.girder import get_girder_db
from isic.ingest.models import Cohort, Zip


@click.command(help='Migrate uploaded zips from Girder ISIC')
def migrate_zips():
    girder_db = get_girder_db()

    for girder_dataset in girder_db['dataset'].find():
        girder_batch_folder = girder_db['folder'].find_one({'_id': girder_dataset['folderId']})

        Cohort.objects.update_or_create(
            girder_id=str(girder_dataset['_id']),
            defaults=dict(
                name=girder_dataset['name'],
                description=girder_dataset['description'],
                created=girder_dataset['created'].replace(tzinfo=datetime.timezone.utc),
                modified=girder_dataset['updated'].replace(tzinfo=datetime.timezone.utc),
            ),
        )

    for girder_batch in girder_db['batch'].find():
        girder_file_id = girder_batch.get('uploadFileId')
        if girder_file_id:
            girder_file = girder_db['file'].find_one({'_id': girder_file_id})

            girder_batch_name = girder_batch.get('originalFilename') or \
                                girder_file['name'].split('/')[-1]

            # TODO: Do not trust Girder for an accurate size
            girder_batch_size = girder_file['size']
            # girder_batch_size_mb = int(girder_batch_size / (2 ** 20))

            girder_batch_created = min(
                girder_batch['created'],
                girder_file['created'],
            ).replace(tzinfo=datetime.timezone.utc)
        else:
            girder_batch_name = girder_batch.get('originalFilename') or ''
            girder_batch_size = None
            girder_batch_created = girder_batch['created'].replace(tzinfo=datetime.timezone.utc)

        # girder_file_resp = requests.get(
        #     f'https://isic-archive.com/api/v1/file/{girder_file_id}/download',
        #     headers={
        #         'girder-token': '',
        #     },
        #     stream=True,
        # )
        # girder_file_resp.raw.seek = lambda _: None
        # girder_file_blob = UploadedFile(
        #     file=girder_file_resp.raw,
        #     name=girder_file_name,
        #     content_type='application/zip',
        #     size=girder_file_size,
        # )

        Zip.objects.update_or_create(
            girder_id=str(girder_batch['_id']),
            defaults=dict(
                cohort=Cohort.objects.filter(girder_id=str(girder_batch['datasetId'])).first(),
                blob=None,
                blob_name=girder_batch_name,
                blob_size=girder_batch_size,
                created=girder_batch_created,
                modified=girder_batch_created,
            ),
        )
