# Generated by Django 4.1.10 on 2023-08-30 13:45
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0046_accession_accession_lesion_id_patient_id_exclusion"),
    ]

    operations = [
        migrations.AddField(
            model_name="metadataversion",
            name="patient",
            field=models.JSONField(default=dict),
        ),
    ]
