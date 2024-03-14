# Generated by Django 3.2.11 on 2022-02-22 00:12
from __future__ import annotations

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0034_auto_20220217_1853"),
        ("studies", "0021_study_owners"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="markup",
            options={},
        ),
        migrations.AlterField(
            model_name="question",
            name="prompt",
            field=models.CharField(max_length=400),
        ),
        migrations.AlterUniqueTogether(
            name="annotation",
            unique_together={("study", "task", "image", "annotator")},
        ),
        migrations.AlterUniqueTogether(
            name="markup",
            unique_together={("annotation", "feature")},
        ),
        migrations.AlterUniqueTogether(
            name="questionchoice",
            unique_together={("question", "text")},
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                condition=models.Q(("official", True)),
                fields=("prompt",),
                name="question_official_prompt_unique",
            ),
        ),
    ]
