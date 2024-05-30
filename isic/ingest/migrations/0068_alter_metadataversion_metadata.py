# Generated by Django 4.2.13 on 2024-05-20 19:02

from django.db import migrations, models

import isic.ingest.utils.json


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0067_accession_accession_unique_rcm_case_id_macroscopic_image"),
    ]

    operations = [
        migrations.AlterField(
            model_name="metadataversion",
            name="metadata",
            field=models.JSONField(encoder=isic.ingest.utils.json.DecimalAwareJSONEncoder),
        ),
    ]