import io

import PIL.Image
from bson import ObjectId
import djclick as click
import requests

from isic.core.models.girder_image import GirderDataset, GirderImage
from isic.core.models.isic_id import IsicId
from isic.ingest.models import Accession, DistinctnessMeasure
from isic.login.girder import create_girder_token, get_girder_db

LESION_IMAGES_ID = ObjectId('55943cff9fc3c13155bcad5e')


@click.command(help='Populate the GirderImage table')
def load_girder_images():
    girder_db = get_girder_db()

    girder_admin_user = girder_db['user'].find_one({'login': 'isic-admin'})
    girder_token = create_girder_token(str(girder_admin_user['_id']))

    with click.progressbar(
        list(girder_db['item'].find({'baseParentId': LESION_IMAGES_ID}))
    ) as items:
        for item in items:
            # Skip existing rows
            if GirderImage.objects.filter(item_id=str(item['_id'])).exists():
                continue

            girder_file = girder_db['file'].find_one(
                {'itemId': item['_id'], 'imageRole': 'original'}
            )
            if not girder_file:
                raise Exception(f'Could not find original file for item_id: {item["_id"]}')

            original_blob_resp = requests.get(
                f'https://isic-archive.com/api/v1/file/{girder_file["_id"]}/download',
                headers={
                    'girder-token': girder_token,
                },
                stream=True,
            )
            original_blob_resp.raise_for_status()

            original_blob_stream = io.BytesIO()
            for chunk in original_blob_resp.iter_content(chunk_size=1024 * 1024 * 5):
                original_blob_stream.write(chunk)
            original_blob_stream.seek(0)

            # Set a larger max size, to accommodate confocal images
            # This uses ~1.1GB of memory
            PIL.Image.MAX_IMAGE_PIXELS = 20_000 * 20_000 * 3
            img = PIL.Image.open(original_blob_stream)
            img = img.convert('RGB')
            stripped_blob_stream = io.BytesIO()
            img.save(stripped_blob_stream, format='JPEG')
            stripped_blob_stream.seek(0)

            girder_image = GirderImage(
                isic=IsicId.objects.get_or_create(id=item['name'])[0],
                item_id=str(item['_id']),
                file_id=str(girder_file['_id']),
                dataset=GirderDataset.get_or_create(item['meta']['datasetId']),
                original_filename=item['privateMeta']['originalFilename'],
                original_file_relpath=item['privateMeta'].get('originalFileRelpath', ''),
                metadata=item['meta']['clinical'],
                unstructured_metadata=item['meta']['unstructured']
                | item['meta'].get('unstructuredExif', {}),
                original_blob_dm=DistinctnessMeasure.compute_checksum(original_blob_stream),
                stripped_blob_dm=DistinctnessMeasure.compute_checksum(stripped_blob_stream),
                accession=Accession.objects.filter(girder_id=str(item['_id'])).first(),
            )
            girder_image.full_clean()
            girder_image.save()
