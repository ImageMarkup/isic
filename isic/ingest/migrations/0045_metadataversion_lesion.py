# Generated by Django 4.1.10 on 2023-08-30 13:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0044_accession_ingest_acce_cohort__e73c08_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="metadataversion",
            name="lesion",
            field=models.JSONField(default=dict),
        ),
    ]
