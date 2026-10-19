from django.conf import settings
from django.contrib.postgres.operations import AddIndexConcurrently
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("ingest", "0044_accession_creator_created_index"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        AddIndexConcurrently(
            model_name="accessionreview",
            index=models.Index(
                fields=["creator", "-reviewed_at"], name="ingest_acce_creator_eac4f4_idx"
            ),
        ),
    ]
