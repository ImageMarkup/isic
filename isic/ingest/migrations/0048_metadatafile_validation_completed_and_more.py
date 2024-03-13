# Generated by Django 4.1.11 on 2023-12-11 22:51
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0047_metadataversion_patient"),
    ]

    operations = [
        migrations.AddField(
            model_name="metadatafile",
            name="validation_completed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="metadatafile",
            name="validation_errors",
            field=models.TextField(blank=True),
        ),
    ]
