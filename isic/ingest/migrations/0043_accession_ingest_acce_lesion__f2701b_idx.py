# Generated by Django 4.1.10 on 2023-08-28 13:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0042_lesion_accession_lesion_lesion_unique_lesion_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="accession",
            index=models.Index(
                fields=["lesion_id", "id", "cohort_id"], name="ingest_acce_lesion__f2701b_idx"
            ),
        ),
    ]