# Generated by Django 5.1 on 2024-08-26 21:05

from django.conf import settings
from django.db import migrations, models
import isic_metadata.fields


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0003_accession_accession_is_cog_mosaic"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="accession",
            name="accession_is_cog_mosaic",
        ),
        migrations.AddConstraint(
            model_name="accession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("is_cog", False),
                    ("image_type__isnull", True),
                    ("image_type", isic_metadata.fields.ImageTypeEnum["rcm_mosaic"]),
                    _connector="OR",
                ),
                name="accession_is_cog_mosaic",
            ),
        ),
    ]
