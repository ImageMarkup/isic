# Generated by Django 5.1.3 on 2024-11-21 14:20

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("studies", "0002_alter_question_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="questionchoice",
            name="text",
            field=models.CharField(max_length=255),
        ),
    ]
