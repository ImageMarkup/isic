# Generated by Django 4.1.13 on 2024-02-16 19:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ingest", "0049_alter_accession_blob_size_alter_accession_height_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="accession",
            name="primary_biopsy",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]