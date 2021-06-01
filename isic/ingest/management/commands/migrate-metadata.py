import datetime
from functools import lru_cache
import pdb
import sys
import traceback

from bson.objectid import ObjectId
from django.db import transaction
import djclick as click
from girder.models.user import User as GirderUser

from isic.ingest.models import Accession, CheckLog
from isic.ingest.validators import MetadataRow
from isic.login.backends import GirderBackend
from isic.login.girder import fetch_girder_user_by_email, get_girder_db
from isic.login.models import Profile


@lru_cache(maxsize=10000)
def import_user(id):
    id = str(id)
    # remap deleted user of Aadi
    if id == '55d5e0ce9fc3c10470dba1a1':
        id = '55d4cde89fc3c1490e995086'

    profile = Profile.objects.filter(girder_id=str(id)).first()
    if profile:
        return profile.user

    username = GirderUser().load(id, force=True)
    if not username:
        return None
    username = username['email']

    girder_user = fetch_girder_user_by_email(username)
    if not girder_user:
        return None

    user = GirderBackend.get_or_create_user_from_girder(girder_user)

    return user


@lru_cache(maxsize=1000000)
def get_folder(folder_id):
    girder_db = get_girder_db()
    folder = girder_db['folder'].find_one({'_id': folder_id})
    return folder


def migrate_reviewed(accession, item):
    if accession.quality_check is not None and accession.phi_check is not None:
        return

    if item['meta'].get('reviewed'):
        review = item['meta']['reviewed']
        assert review['accepted']
        with transaction.atomic():
            accession.phi_check = True
            accession.quality_check = True
            accession.save(update_fields=['phi_check', 'quality_check'])

            reviewer = import_user(review['userId'])
            assert reviewer

            for field in ['phi_check', 'quality_check']:
                log = accession.checklogs.create(
                    creator=reviewer, change_field=field, change_to=True
                )
                CheckLog.objects.filter(pk=log.pk).update(
                    created=review['time'].replace(tzinfo=datetime.timezone.utc),
                    modified=review['time'].replace(tzinfo=datetime.timezone.utc),
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
    if accession.upload.cohort.id == 180:
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
        print(accession.upload.cohort.name, e)
    else:
        accession.save(update_fields=['metadata'])


@click.command(help='Migrate image metadata from Girder ISIC')
def migrate_metadata():
    girder_db = get_girder_db()

    accessions = Accession.objects.select_related('upload__cohort').exclude(girder_id='')
    num_accessions = accessions.count()

    import random

    accessions = list(accessions)
    random.shuffle(accessions)
    for i, accession in enumerate(accessions):
        if i % 100 == 0:
            print(f'{i}/{num_accessions}')

        item = girder_db['item'].find_one(
            {'_id': ObjectId(accession.girder_id)},
        )
        assert item
        try:
            # migrate tags
            if item['meta'].get('tags', []):
                accession.tags = item['meta']['tags']
                accession.save(update_fields=['tags'])

            accession.metadata = {}
            accession.unstructured_metadata = {}

            migrate_reviewed(accession, item)
            migrate_unstructured_and_exif(accession, item)
            migrate_clinical_metadata(accession, item)
        except Exception:
            _, _, tb = sys.exc_info()
            traceback.print_exc()
            pdb.post_mortem(tb)
