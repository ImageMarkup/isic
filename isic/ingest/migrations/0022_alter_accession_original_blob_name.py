# Generated by Django 4.0.3 on 2022-05-09 13:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0021_auto_20220509_1337"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accession",
            name="original_blob_name",
            field=models.CharField(db_index=True, editable=False, max_length=255),
        ),
    ]
