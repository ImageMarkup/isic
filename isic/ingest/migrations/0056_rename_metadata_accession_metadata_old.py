# Generated by Django 4.1.13 on 2024-02-29 18:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0055_accession_accession_concomitant_biopsy_diagnosis_confirm_type"),
    ]

    operations = [
        migrations.RenameField(
            model_name="accession",
            old_name="metadata",
            new_name="metadata_old",
        ),
    ]