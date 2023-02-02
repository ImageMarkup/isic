# Generated by Django 3.2.6 on 2021-09-27 22:50

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_collection_public"),
    ]

    operations = [
        migrations.AlterField(
            model_name="imageredirect",
            name="image",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="aliases", to="core.image"
            ),
        ),
        migrations.RenameModel("ImageRedirect", "ImageAlias"),
    ]
