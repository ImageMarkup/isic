# Generated by Django 5.1.8 on 2025-05-01 16:30

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0019_accession_attribution"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accession",
            name="valid_legacy_dx",
        ),
        migrations.RemoveIndex(
            model_name="accession",
            name="ingest_acce_legacy__33310d_idx",
        ),
        migrations.RemoveField(
            model_name="accession",
            name="legacy_dx",
        ),
    ]
