import django.core.validators
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef, Subquery
import django.db.models.deletion

import isic.core.models.doi


def invert_doi_fk(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor):
    Doi = apps.get_model("core", "Doi")
    Collection = apps.get_model("core", "Collection")

    Doi.objects.update(
        collection=Subquery(Collection.objects.filter(doi=OuterRef("pk")).values("pk")[:1])
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_alter_collection_shares_alter_image_shares"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collection",
            name="doi",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="collection_reverse",
                to="core.doi",
            ),
        ),
        migrations.AddField(
            model_name="doi",
            name="collection",
            field=models.OneToOneField(
                default=None,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="core.collection",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(invert_doi_fk, elidable=True),
        migrations.RemoveField(
            model_name="collection",
            name="doi",
        ),
        migrations.AlterField(
            model_name="doi",
            name="collection",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                to="core.collection",
            ),
        ),
        migrations.AlterField(
            model_name="doi",
            name="id",
            field=models.CharField(
                default=isic.core.models.doi._generate_random_doi_id,  # noqa: SLF001
                max_length=30,
                primary_key=True,
                serialize=False,
                validators=[django.core.validators.RegexValidator("^\\d+\\.\\d+/\\d+$")],
            ),
        ),
        migrations.RemoveField(
            model_name="doi",
            name="url",
        ),
    ]
