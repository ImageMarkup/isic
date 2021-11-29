import hashlib
import io

from django.core.files.uploadedfile import InMemoryUploadedFile
import djclick as click

from isic.studies.models import Markup


@click.command(help='Migrate masks')
def migrate_masks():
    with click.progressbar(Markup.objects.filter(mask_blob=None).only('mask').all()) as markups:
        for markup in markups:
            stream = io.BytesIO(markup.mask)
            markup.mask_blob = InMemoryUploadedFile(
                file=stream,
                field_name=None,
                name='mask.png',
                content_type='image/jpg',
                size=stream.getbuffer().nbytes,
                charset=None,
            )
            markup.save(update_fields=['mask_blob'])

    with click.progressbar(Markup.objects.only('mask', 'mask_blob').all()) as markups:
        for markup in markups:
            assert (
                hashlib.sha1(markup.mask).hexdigest()
                == hashlib.sha1(markup.mask_blob.open().read()).hexdigest()
            )
