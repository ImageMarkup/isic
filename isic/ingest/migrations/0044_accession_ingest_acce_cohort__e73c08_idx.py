# Generated by Django 4.1.10 on 2023-08-28 13:31
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0043_accession_ingest_acce_lesion__f2701b_idx"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                fields=["cohort_id", "status", "created"], name="ingest_acce_cohort__e73c08_idx"
            ),
        ),
    ]
