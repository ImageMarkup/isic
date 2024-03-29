# Generated by Django 3.1.2 on 2020-10-16 18:33
from __future__ import annotations

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import django_extensions.db.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Annotation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "annotator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Feature",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("required", models.BooleanField(default=False)),
                (
                    "name",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.CharField(max_length=200), size=None
                    ),
                ),
                ("official", models.BooleanField()),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Image",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("object_id", models.CharField(max_length=24, unique=True)),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("required", models.BooleanField(default=True)),
                ("prompt", models.CharField(max_length=400, unique=True)),
                (
                    "type",
                    models.CharField(
                        choices=[("select", "Select")], default="select", max_length=6
                    ),
                ),
                ("official", models.BooleanField()),
            ],
            options={
                "ordering": ["prompt"],
            },
        ),
        migrations.CreateModel(
            name="QuestionChoice",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("text", models.CharField(max_length=100)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="studies.question",
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Study",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                ("description", models.TextField()),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL
                    ),
                ),
                ("features", models.ManyToManyField(to="studies.Feature")),
                ("questions", models.ManyToManyField(to="studies.Question")),
            ],
            options={
                "verbose_name_plural": "Studies",
            },
        ),
        migrations.CreateModel(
            name="StudyTask",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "annotator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, to="studies.image"
                    ),
                ),
                (
                    "study",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="tasks",
                        to="studies.study",
                    ),
                ),
            ],
            options={
                "unique_together": {("study", "annotator", "image")},
            },
        ),
        migrations.CreateModel(
            name="Response",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                (
                    "annotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="studies.annotation",
                    ),
                ),
                (
                    "choice",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="studies.questionchoice"
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="responses",
                        to="studies.question",
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Markup",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "created",
                    django_extensions.db.fields.CreationDateTimeField(
                        auto_now_add=True, verbose_name="created"
                    ),
                ),
                (
                    "modified",
                    django_extensions.db.fields.ModificationDateTimeField(
                        auto_now=True, verbose_name="modified"
                    ),
                ),
                ("mask", models.BinaryField()),
                ("present", models.BooleanField()),
                (
                    "annotation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="markups",
                        to="studies.annotation",
                    ),
                ),
                (
                    "feature",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="markups",
                        to="studies.feature",
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="annotation",
            name="image",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to="studies.image"
            ),
        ),
        migrations.AddField(
            model_name="annotation",
            name="study",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="studies.study"
            ),
        ),
        migrations.AddField(
            model_name="annotation",
            name="task",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="annotation",
                to="studies.studytask",
            ),
        ),
    ]
