# Generated by Django 3.2.9 on 2021-11-29 07:37

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0017_rename_mask_blob_markup_mask"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="response",
            options={},
        ),
        migrations.AlterUniqueTogether(
            name="response",
            unique_together={("annotation", "question")},
        ),
    ]
