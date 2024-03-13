# Generated by Django 4.0.3 on 2022-04-17 17:53
from __future__ import annotations

from django.db import migrations
from django.db.models.expressions import F


def migrate_reviewed_at(apps, schema_editor):
    AccessionReview = apps.get_model("ingest", "AccessionReview")
    AccessionReview.objects.update(reviewed_at=F("created"))


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0014_accessionreview_reviewed_at"),
    ]

    operations = [migrations.RunPython(migrate_reviewed_at)]
