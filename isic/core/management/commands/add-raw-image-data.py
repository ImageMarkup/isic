import json

from bson import ObjectId
from bson.json_util import dumps
import djclick as click

from isic.core.models.girder_image import GirderImage
from isic.login.girder import get_girder_db

LESION_IMAGES_ID = ObjectId('55943cff9fc3c13155bcad5e')


@click.command(help='Fill the GirderImage table with raw mongo data.')
def add_raw_image_data():
    girder_db = get_girder_db()

    with click.progressbar(
        list(girder_db['item'].find({'baseParentId': LESION_IMAGES_ID}))
    ) as items:
        for item in items:
            girder_image = GirderImage.objects.get(item_id=str(item['_id']))
            girder_image.raw = json.loads(dumps(item))
            girder_image.save(update_fields=['raw'])
