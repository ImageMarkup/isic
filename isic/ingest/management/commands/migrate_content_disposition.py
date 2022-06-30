import boto3
from django.conf import settings
import djclick as click

from isic.core.models import Segmentation
from isic.ingest.models import Accession
from isic.studies.models import Markup

client = boto3.client('s3')


def make_attachment(key):
    client.copy_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=key,
        CopySource=f'{settings.AWS_STORAGE_BUCKET_NAME}/{key}',
        ContentDisposition='attachment',
        # Content-Disposition is metadata, so it needs to be "replaced"
        MetadataDirective='REPLACE',
    )


@click.command()
def migrate_content_disposition():
    accessions = Accession.objects.ingested()
    with click.progressbar(accessions.iterator(), length=accessions.count()) as bar:
        for accession in bar:
            make_attachment(accession.blob.name)
            make_attachment(accession.original_blob.name)
            make_attachment(accession.thumbnail_256.name)

    segmentations = Segmentation.objects.all()
    with click.progressbar(segmentations.iterator(), length=segmentations.count()) as bar:
        for segmentation in bar:
            make_attachment(segmentation.mask.name)

    markups = Markup.objects.all()
    with click.progressbar(markups.iterator(), length=markups.count()) as bar:
        for markup in bar:
            make_attachment(markup.mask.name)
