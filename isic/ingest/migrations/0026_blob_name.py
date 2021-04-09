import os

from django.db import migrations


def clean_blob_name(apps, schema_editor):
    Zip = apps.get_model('ingest', 'Zip')  # noqa: N806
    MetadataFile = apps.get_model('ingest', 'MetadataFile')  # noqa: N806

    for zip in Zip.objects.all():
        zip.blob_name = os.path.basename(zip.blob_name)
        zip.save(update_fields=['blob_name'])

    for metadata_file in MetadataFile.objects.all():
        metadata_file.blob_name = os.path.basename(metadata_file.blob_name)
        metadata_file.save(update_fields=['blob_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0025_alter_zip_status'),
    ]

    operations = [
        migrations.RunPython(clean_blob_name),
    ]
