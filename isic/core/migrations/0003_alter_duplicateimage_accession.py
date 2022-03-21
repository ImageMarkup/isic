# Generated by Django 3.2 on 2021-05-10 14:39

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0001_initial_squashed'),
        ('core', '0002_alter_duplicateimage_accession'),
    ]

    operations = [
        migrations.AlterField(
            model_name='duplicateimage',
            name='accession',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='duplicates',
                to='ingest.accession',
            ),
        ),
    ]
