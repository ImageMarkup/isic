# Generated by Django 5.1.9 on 2025-06-04 16:14

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0001_initial_squashed_0032_alter_metadataversion_created_and_more"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="distinctnessmeasure",
            options={"get_latest_by": "modified"},
        ),
        migrations.RemoveIndex(
            model_name="distinctnessmeasure",
            name="ingest_dist_checksu_cde183_idx",
        ),
    ]
