# Generated by Django 4.0.3 on 2022-03-22 16:33
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0001_initial_squashed"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accession",
            name="accession_wh_status_check",
        ),
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("blob_size__isnull", False),
                        ("height__isnull", False),
                        ("status", "succeeded"),
                        ("width__isnull", False),
                    ),
                    models.Q(("status", "succeeded"), _negated=True),
                    _connector="OR",
                ),
                name="accession_succeeded_blob_fields",
            ),
        ),
    ]
