# Generated by Django 3.2.6 on 2021-10-07 17:37

import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0025_alter_imagealias_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='Doi',
            fields=[
                (
                    'created',
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name='created'
                    ),
                ),
                (
                    'modified',
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name='modified'
                    ),
                ),
                (
                    'id',
                    models.CharField(
                        max_length=30,
                        primary_key=True,
                        serialize=False,
                        validators=[django.core.validators.RegexValidator('^\\d+\\.\\d+/\\d+$')],
                    ),
                ),
                ('url', models.CharField(max_length=200)),
            ],
            options={
                'get_latest_by': 'modified',
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='collection',
            name='doi',
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='core.doi'
            ),
        ),
    ]
