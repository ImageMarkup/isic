# Generated by Django 3.2.11 on 2022-02-23 01:44

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0027_auto_20220223_0136"),
    ]

    operations = [
        migrations.AddField(
            model_name="studyquestion",
            name="required",
            field=models.BooleanField(null=True),
        ),
    ]
