# Generated by Django 4.2.13 on 2024-07-11 15:22

from django.db import migrations, models
import isic_metadata.fields


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0002_accession_is_cog"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("image_type__isnull", True),
                    models.Q(
                        (
                            "image_type",
                            isic_metadata.fields.ImageTypeEnum["rcm_mosaic"],
                        ),
                        _negated=True,
                    ),
                    ("is_cog", True),
                    _connector="OR",
                ),
                name="accession_is_cog_mosaic",
            ),
        ),
    ]
