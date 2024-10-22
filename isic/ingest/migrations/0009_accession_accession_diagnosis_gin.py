# Generated by Django 5.1.1 on 2024-10-07 17:40

from django.conf import settings
import django.contrib.postgres.indexes
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0008_accession_accession_rounded_age"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddIndex(
            model_name="accession",
            index=django.contrib.postgres.indexes.GinIndex(
                django.contrib.postgres.indexes.OpClass("diagnosis", name="gin_trgm_ops"),
                name="accession_diagnosis_gin",
            ),
        ),
    ]