# Generated by Django 4.0.3 on 2022-05-22 01:58

from django.db import migrations, models
import django.db.models.expressions


class Migration(migrations.Migration):
    dependencies = [
        ('ingest', '0026_auto_20220522_0154'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accession',
            name='blob_name',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=255),
        ),
        migrations.AddConstraint(
            model_name='accession',
            constraint=models.CheckConstraint(
                check=models.Q(
                    ('original_blob_name', django.db.models.expressions.F('blob_name')),
                    _negated=True,
                ),
                name='accession_blob_name_not_original_blob_name',
            ),
        ),
    ]
