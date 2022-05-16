# Generated by Django 4.0.3 on 2022-04-26 21:01

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0017_remove_metadataversion_metadata_version_needs_meta_or_unstructured_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accessionreview',
            name='accession',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='review',
                to='ingest.accession',
            ),
        ),
    ]