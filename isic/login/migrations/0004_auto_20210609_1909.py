# Generated by Django 3.2.3 on 2021-06-09 19:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('login', '0003_remove_profile_email_verified'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='girder_salt',
            field=models.CharField(blank=True, default='', max_length=60),
            preserve_default=False,
        ),
    ]