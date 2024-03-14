# Generated by Django 4.0.3 on 2022-05-22 01:37
from __future__ import annotations

from django.db import migrations

from isic.ingest.models.accession import AccessionStatus


def reset_blob_name(apps, schema_editor):
    Accession = apps.get_model("ingest", "Accession")
    Accession.objects.exclude(status=AccessionStatus.SUCCEEDED).update(blob_name="")


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0025_alter_accession_unique_together"),
    ]

    operations = [migrations.RunPython(reset_blob_name)]
