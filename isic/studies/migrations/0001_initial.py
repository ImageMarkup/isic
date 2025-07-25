# Generated by Django 4.2.13 on 2024-06-25 19:44

from django.conf import settings
import django.contrib.postgres.fields
from django.db import migrations, models
import django.db.models.deletion
import django.db.models.lookups
import django_extensions.db.fields
import s3_file_field.fields

import isic.core.storages.utils


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Annotation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("start_time", models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Feature",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Markup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                    "mask",
                    s3_file_field.fields.S3FileField(
                        upload_to=isic.core.storages.utils.generate_upload_to
                    ),
                ),
                ("present", models.BooleanField()),
            ],
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("prompt", models.CharField(max_length=400)),
                (
                    "type",
                    models.CharField(
                        choices=[("select", "Select"), ("number", "Number")],
                        default="select",
                        max_length=6,
                    ),
                ),
                ("official", models.BooleanField()),
            ],
            options={
                "ordering": ["prompt"],
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="QuestionChoice",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("attribution", models.CharField(max_length=200)),
                (
                    "name",
                    models.CharField(
                        help_text="The name for your Study.",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="A description of the methodology behind your Study.",
                    ),
                ),
                (
                    "public",
                    models.BooleanField(
                        default=False,
                        help_text="Whether or not your Study will be public. A study can only be public if the images it uses are also public.",  # noqa: E501
                    ),
                ),
                (
                    "collection",
                    models.ForeignKey(
                        help_text="The Collection of images to use in your Study.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="studies",
                        to="core.collection",
                    ),
                ),
                (
                    "creator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("features", models.ManyToManyField(to="studies.feature")),
                (
                    "owners",
                    models.ManyToManyField(
                        related_name="owned_studies", to=settings.AUTH_USER_MODEL
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Studies",
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="StudyTask",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "image",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.image"),
                ),
                (
                    "study",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tasks",
                        to="studies.study",
                    ),
                ),
            ],
            options={
                "get_latest_by": "modified",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="StudyQuestion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("required", models.BooleanField()),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="studies.question",
                    ),
                ),
                (
                    "study",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="studies.study"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="study",
            name="questions",
            field=models.ManyToManyField(through="studies.StudyQuestion", to="studies.question"),
        ),
        migrations.CreateModel(
            name="Response",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
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
                ("value", models.JSONField(null=True)),
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
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="studies.questionchoice",
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
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                condition=models.Q(("official", True)),
                fields=("prompt",),
                name="question_official_prompt_unique",
            ),
        ),
        migrations.AddField(
            model_name="markup",
            name="annotation",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="markups",
                to="studies.annotation",
            ),
        ),
        migrations.AddField(
            model_name="markup",
            name="feature",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="markups",
                to="studies.feature",
            ),
        ),
        migrations.AddField(
            model_name="annotation",
            name="annotator",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AddField(
            model_name="annotation",
            name="image",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.image"),
        ),
        migrations.AddField(
            model_name="annotation",
            name="study",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="annotations",
                to="studies.study",
            ),
        ),
        migrations.AddField(
            model_name="annotation",
            name="task",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="annotation",
                to="studies.studytask",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="studytask",
            unique_together={("study", "annotator", "image")},
        ),
        migrations.AlterUniqueTogether(
            name="studyquestion",
            unique_together={("study", "question")},
        ),
        migrations.AddConstraint(
            model_name="response",
            constraint=models.CheckConstraint(
                condition=django.db.models.lookups.Exact(
                    lhs=models.Func(
                        "choice",
                        "value",
                        function="num_nonnulls",
                        output_field=models.IntegerField(),
                    ),
                    rhs=models.Value(1),
                ),
                name="response_choice_or_value_check",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="response",
            unique_together={("annotation", "question")},
        ),
        migrations.AlterUniqueTogether(
            name="questionchoice",
            unique_together={("question", "text")},
        ),
        migrations.AlterUniqueTogether(
            name="markup",
            unique_together={("annotation", "feature")},
        ),
        migrations.AddConstraint(
            model_name="annotation",
            constraint=models.CheckConstraint(
                condition=models.Q(("start_time__lte", models.F("created"))),
                name="annotation_start_time_check",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="annotation",
            unique_together={("study", "task", "image", "annotator")},
        ),
    ]
