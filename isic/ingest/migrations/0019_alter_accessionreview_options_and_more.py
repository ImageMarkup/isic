# Generated by Django 4.0.3 on 2022-04-26 21:16

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0018_alter_accessionreview_accession'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='accessionreview',
            options={'get_latest_by': 'reviewed_at', 'ordering': ['-reviewed_at']},
        ),
        migrations.RemoveField(
            model_name='accessionreview',
            name='created',
        ),
        migrations.RemoveField(
            model_name='accessionreview',
            name='modified',
        ),
        migrations.AlterField(
            model_name='accessionreview',
            name='reviewed_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]
