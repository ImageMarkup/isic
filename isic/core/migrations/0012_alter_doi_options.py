# Generated by Django 5.1.5 on 2025-02-19 17:34

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_doi_metadata_doi_metadata_size"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="doi",
            options={"verbose_name": "DOI", "verbose_name_plural": "DOIs"},
        ),
    ]
