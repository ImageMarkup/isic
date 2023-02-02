# Generated by Django 4.0.5 on 2022-07-03 22:28

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0032_remove_accession_accession_succeeded_blob_fields_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accession",
            name="accession_succeeded_blob_fields",
        ),
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("blob_size__isnull", False),
                        ("height__isnull", False),
                        ("status", "succeeded"),
                        ("thumbnail_256_size__isnull", False),
                        ("width__isnull", False),
                        models.Q(("thumbnail_256", ""), _negated=True),
                        models.Q(("blob_name", ""), _negated=True),
                    ),
                    models.Q(("status", "succeeded"), _negated=True),
                    _connector="OR",
                ),
                name="accession_succeeded_blob_fields",
            ),
        ),
    ]
