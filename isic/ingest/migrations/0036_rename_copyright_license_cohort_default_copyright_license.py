# Generated by Django 4.1.10 on 2023-07-31 22:10

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ingest", "0035_zipupload_zipupload_unique_blob"),
    ]

    operations = [
        migrations.RenameField(
            model_name="cohort",
            old_name="copyright_license",
            new_name="default_copyright_license",
        ),
    ]