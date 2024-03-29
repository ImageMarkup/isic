# Generated by Django 3.2 on 2021-05-25 09:34
from __future__ import annotations

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion

import isic.core.models.isic_id


def copy_isic_id(apps, schema_editor):
    IsicId = apps.get_model("core", "IsicId")

    Image = apps.get_model("core", "Image")
    for image in Image.objects.all():
        isic_id = IsicId.objects.create(id=image.isic_id_string)

        image.isic = isic_id
        image.save(update_fields=["isic"])

    DuplicateImage = apps.get_model("core", "DuplicateImage")
    ImageRedirect = apps.get_model("core", "ImageRedirect")
    for duplicate_image in DuplicateImage.objects.all():
        isic_id = IsicId.objects.create(id=duplicate_image.isic_id_string)

        duplicate_image.isic = isic_id
        duplicate_image.save(update_fields=["isic"])

        image_redirect = ImageRedirect.objects.get(isic_id_string=duplicate_image.isic_id_string)
        image_redirect.isic = isic_id
        image_redirect.save(update_fields=["isic"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_alter_collection_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="IsicId",
            fields=[
                (
                    "id",
                    models.CharField(
                        default=isic.core.models.isic_id._default_id,  # noqa: SLF001
                        max_length=12,
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.RegexValidator("^ISIC_[0-9]{7}$")],
                        verbose_name="ISIC ID",
                    ),
                ),
            ],
        ),
        # Rename fields to avoid column name conflicts
        migrations.RenameField(
            model_name="image",
            old_name="isic_id",
            new_name="isic_id_string",
        ),
        migrations.RenameField(
            model_name="duplicateimage",
            old_name="isic_id",
            new_name="isic_id_string",
        ),
        migrations.RenameField(
            model_name="imageredirect",
            old_name="isic_id",
            new_name="isic_id_string",
        ),
        # Add a null version of the new field
        migrations.AddField(
            model_name="image",
            name="isic",
            field=models.OneToOneField(
                null=True, on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        migrations.AddField(
            model_name="duplicateimage",
            name="isic",
            field=models.OneToOneField(
                null=True, on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        migrations.AddField(
            model_name="imageredirect",
            name="isic",
            field=models.OneToOneField(
                null=True, on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        # Copy from the old field to the new field
        migrations.RunPython(copy_isic_id),
        # Make the new field non-nullable
        migrations.AlterField(
            model_name="image",
            name="isic",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        migrations.AlterField(
            model_name="duplicateimage",
            name="isic",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        migrations.AlterField(
            model_name="imageredirect",
            name="isic",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT, to="core.isicid"
            ),
        ),
        # Remove the old field
        migrations.RemoveField(
            model_name="image",
            name="isic_id_string",
        ),
        migrations.RemoveField(
            model_name="duplicateimage",
            name="isic_id_string",
        ),
        migrations.RemoveField(
            model_name="imageredirect",
            name="isic_id_string",
        ),
        # Add a default to the new field state
        migrations.AlterField(
            model_name="image",
            name="isic",
            field=models.OneToOneField(
                default=isic.core.models.isic_id.IsicId.safe_create,
                on_delete=django.db.models.deletion.PROTECT,
                to="core.isicid",
            ),
        ),
    ]
