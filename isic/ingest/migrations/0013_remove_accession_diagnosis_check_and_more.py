# Generated by Django 4.0.3 on 2022-04-16 22:56

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('ingest', '0012_alter_accessionreview_accession'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='accession',
            name='diagnosis_check',
        ),
        migrations.RemoveField(
            model_name='accession',
            name='duplicate_check',
        ),
        migrations.RemoveField(
            model_name='accession',
            name='lesion_check',
        ),
        migrations.RemoveField(
            model_name='accession',
            name='phi_check',
        ),
        migrations.RemoveField(
            model_name='accession',
            name='quality_check',
        ),
    ]
