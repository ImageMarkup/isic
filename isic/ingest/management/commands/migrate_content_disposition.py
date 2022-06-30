import boto3
from django.conf import settings
from django.db import transaction
import djclick as click

from isic.ingest.models import Accession

client = boto3.client('s3')


@click.command()
def migrate_content_disposition():
    with transaction.atomic():
        accessions = Accession.objects.all()

        with click.progressbar(accessions.iterator(), length=accessions.count()) as bar:
            for accession in bar:

                client.copy_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=accession.blob.name,
                    CopySource=f'{settings.AWS_STORAGE_BUCKET_NAME}/{accession.blob.name}',
                    ContentDisposition='attachment',
                    # Content-Disposition is metadata, so it needs to be "replaced"
                    MetadataDirective='REPLACE',
                )
