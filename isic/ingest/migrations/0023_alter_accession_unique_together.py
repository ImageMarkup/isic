# Generated by Django 4.0.3 on 2022-05-09 14:51

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0022_alter_accession_original_blob_name"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="accession",
            unique_together={("cohort", "blob_name"), ("cohort", "original_blob_name")},
        ),
    ]
