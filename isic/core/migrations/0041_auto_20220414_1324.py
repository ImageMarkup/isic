# Generated by Django 4.0.3 on 2022-04-14 13:24

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_remove_collection_collection_official_has_unique_name_and_more"),
    ]

    operations = [TrigramExtension()]
