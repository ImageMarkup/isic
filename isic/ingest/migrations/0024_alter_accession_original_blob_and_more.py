# Generated by Django 4.0.3 on 2022-05-09 19:36

from django.db import migrations, models
import s3_file_field.fields


class Migration(migrations.Migration):
    dependencies = [
        ('ingest', '0023_alter_accession_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='accession',
            name='original_blob',
            field=s3_file_field.fields.S3FileField(unique=True),
        ),
        migrations.AddConstraint(
            model_name='accession',
            constraint=models.UniqueConstraint(
                condition=models.Q(('blob', ''), _negated=True),
                fields=('blob',),
                name='accession_unique_blob',
            ),
        ),
    ]
