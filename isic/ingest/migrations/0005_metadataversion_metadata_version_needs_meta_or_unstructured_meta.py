# Generated by Django 4.0.3 on 2022-03-31 21:21

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0004_rename_metadatarevision_metadataversion"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="metadataversion",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("metadata__isnull", True),
                        ("unstructured_metadata__isnull", True),
                        _negated=True,
                    ),
                    models.Q(("metadata", {}), ("unstructured_metadata", {}), _negated=True),
                ),
                name="metadata_version_needs_meta_or_unstructured_meta",
            ),
        ),
    ]
