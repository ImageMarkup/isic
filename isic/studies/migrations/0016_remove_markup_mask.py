# Generated by Django 3.2.9 on 2021-11-29 06:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('studies', '0015_alter_markup_mask_blob'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='markup',
            name='mask',
        ),
    ]
