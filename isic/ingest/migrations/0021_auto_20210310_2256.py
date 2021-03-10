# Generated by Django 3.1.4 on 2021-03-10 22:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0020_auto_20210309_2108'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contributor',
            name='default_attribution',
            field=models.CharField(
                blank=True,
                help_text='Text which must be reproduced by users of your images, to comply with Creative Commons Attribution requirements.',
                max_length=255,
                verbose_name='Default Attribution',
            ),
        ),
    ]
