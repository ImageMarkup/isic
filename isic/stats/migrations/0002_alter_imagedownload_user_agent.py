# Generated by Django 4.0.3 on 2022-04-04 15:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stats', '0001_initial_squashed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='imagedownload',
            name='user_agent',
            field=models.CharField(max_length=400, null=True),
        ),
    ]
