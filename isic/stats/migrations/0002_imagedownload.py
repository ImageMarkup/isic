# Generated by Django 3.2.11 on 2022-03-05 08:23

from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0034_auto_20220217_1853'),
        ('stats', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageDownload',
            fields=[
                (
                    'id',
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name='ID'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, db_index=True
                    ),
                ),
                ('download_time', models.DateTimeField()),
                ('ip_address', models.GenericIPAddressField()),
                ('request_id', models.CharField(max_length=200, unique=True)),
                (
                    'image',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='downloads',
                        to='core.image',
                    ),
                ),
            ],
            options={
                'ordering': ['-created'],
                'get_latest_by': 'created',
                'abstract': False,
            },
        ),
    ]
