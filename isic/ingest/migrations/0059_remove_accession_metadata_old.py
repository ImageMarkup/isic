# Generated by Django 4.1.13 on 2024-03-09 05:04

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0058_migrate_metadata"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="accession",
            name="metadata_old",
        ),
    ]
