# Generated by Django 3.1.4 on 2021-03-09 21:08
# flake8: noqa

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ingest', '0019_auto_20210223_1745'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cohort',
            name='description',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='default_attribution',
            field=models.CharField(blank=True, help_text='Text which must be reproduced by users of your images, to comply with CreativeCommons Attribution requirements.', max_length=255, verbose_name='Default Attribution'),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='default_copyright_license',
            field=models.CharField(blank=True, choices=[('CC-0', 'CC-0'), ('CC-BY', 'CC-BY'), ('CC-BY-NC', 'CC-BY-NC')], max_length=255, verbose_name='Default Copyright License'),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='institution_name',
            field=models.CharField(help_text='The full name of your affiliated institution. <strong>This is private</strong>, and will not be published along with your images.', max_length=255, verbose_name='Institution Name'),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='institution_url',
            field=models.URLField(blank=True, help_text='The URL of your affiliated institution. <strong>This is private</strong>, and will not be published along with your images.', verbose_name='Institution URL'),
        ),
        migrations.AlterField(
            model_name='contributor',
            name='legal_contact_info',
            field=models.TextField(help_text='The person or institution responsible for legal inquiries about your data. <strong> This is private</strong>, and will not be published along with your images.', verbose_name='Legal Contact Information'),
        ),
    ]
