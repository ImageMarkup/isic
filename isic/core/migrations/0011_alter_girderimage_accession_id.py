# Generated by Django 3.2.3 on 2021-06-03 17:07
from __future__ import annotations

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0001_initial_squashed"),
        ("core", "0010_auto_20210602_1835"),
    ]

    operations = [
        migrations.AlterField(
            model_name="girderimage",
            name="accession_id",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="ingest.accession",
            ),
        ),
    ]
