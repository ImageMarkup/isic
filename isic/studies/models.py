import csv
from datetime import timedelta
from typing import Optional

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Case, CharField, Value, When
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.expressions import F, Func
from django.db.models.fields import IntegerField
from django.db.models.functions import Cast
from django.db.models.lookups import Exact
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.forms.fields import CharField as FormCharField, ChoiceField
from django.forms.widgets import RadioSelect
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from s3_file_field.fields import S3FileField

from isic.core.models import Image
from isic.core.models.collection import Collection
from isic.core.storage import generate_upload_to


class Question(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        ordering = ["prompt"]
        constraints = [
            UniqueConstraint(
                name="question_official_prompt_unique",
                fields=["prompt"],
                condition=Q(official=True),
            )
        ]

    class QuestionType(models.TextChoices):
        SELECT = "select", "Select"
        NUMBER = "number", "Number"

    prompt = models.CharField(max_length=400)
    type = models.CharField(max_length=6, choices=QuestionType.choices, default=QuestionType.SELECT)
    official = models.BooleanField()
    # TODO: maybe add a default field

    def __str__(self) -> str:
        return self.prompt

    def to_form_field(self, required: bool):
        if self.type == self.QuestionType.SELECT:
            return ChoiceField(
                required=required,
                choices=[(choice.pk, choice.text) for choice in self.choices.all()],
                label=self.prompt,
                widget=RadioSelect,
            )
        elif self.type == self.QuestionType.NUMBER:
            # TODO: Use floatfield/intfield
            return FormCharField(
                required=required,
                label=self.prompt,
            )

    def save(self, **kwargs):
        from isic.studies.models import Annotation

        if (
            self.pk
            and Annotation.objects.filter(study__in=Study.objects.filter(questions=self)).exists()
        ):
            raise ValidationError("Can't modify the question, someone has already answered it.")

        return super().save(**kwargs)


class QuestionChoice(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        unique_together = [["question", "text"]]

    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.text

    def save(self, **kwargs):
        from isic.studies.models import Annotation

        if (
            self.pk
            and Annotation.objects.filter(
                study__in=Study.objects.filter(question=self.question)
            ).exists()
        ):
            raise ValidationError(
                "Can't modify the choice, the question has already been answered."
            )

        return super().save(**kwargs)


class Feature(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        ordering = ["name"]

    required = models.BooleanField(default=False)
    name = ArrayField(models.CharField(max_length=200))
    official = models.BooleanField()

    @property
    def label(self) -> str:
        return " : ".join(self.name)

    def __str__(self) -> str:
        return self.label

    def save(self, **kwargs):
        from isic.studies.models import Annotation

        if (
            self.pk
            and Annotation.objects.filter(study__in=Study.objects.filter(features=self)).exists()
        ):
            raise ValidationError("Can't modify the feature, someone has already annotated it.")

        return super().save(**kwargs)


class StudyQuerySet(models.QuerySet):
    def public(self):
        return self.filter(public=True)

    def private(self):
        return self.filter(public=False)


class Study(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        verbose_name_plural = "Studies"

    creator = models.ForeignKey(User, on_delete=models.PROTECT)
    owners = models.ManyToManyField(User, related_name="owned_studies")
    attribution = models.CharField(max_length=200)

    name = models.CharField(max_length=100, unique=True, help_text="The name for your Study.")
    description = models.TextField(help_text="A description of the methodology behind your Study.")

    # TODO: refactor code to get images from here instead of inspecting study tasks
    collection = models.ForeignKey(
        Collection,
        on_delete=models.PROTECT,
        related_name="studies",
        help_text="The Collection of images to use in your Study.",
    )

    features = models.ManyToManyField(Feature)
    questions = models.ManyToManyField(Question, through="StudyQuestion")

    # public study means that all images in the study must be public
    # and all of the related data to the study is public (responses).
    # if a study is private, only the owners can see the responses of
    # a study.
    # TODO: implement public checking
    public = models.BooleanField(
        default=False,
        help_text=(
            "Whether or not your Study will be public. A study can only be public if "
            "the images it uses are also public."
        ),
    )

    objects = StudyQuerySet.as_manager()

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("study-detail", args=[self.pk])

    def write_responses_csv(self, stream) -> None:
        fieldnames = ["image", "annotator", "annotation_duration", "question", "answer"]
        writer = csv.DictWriter(stream, fieldnames)

        writer.writeheader()

        for response in Response.objects.filter(annotation__study=self).for_display():
            writer.writerow({field: response[field] for field in fieldnames})


class StudyQuestion(models.Model):
    class Meta:
        unique_together = [["study", "question"]]

    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    order = models.PositiveSmallIntegerField(default=0)
    required = models.BooleanField()


class StudyPermissions:
    model = Study
    perms = ["view_study", "view_study_results"]
    filters = {"view_study": "view_study_list", "view_study_results": "view_study_results_list"}

    @staticmethod
    def view_study_results_list(
        user_obj: User, qs: QuerySet[Study] | None = None
    ) -> QuerySet[Study]:
        qs: QuerySet[Study] = qs if qs is not None else Study._default_manager.all()

        # There's duplication of this check in study_detail.html
        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            return qs.filter(Q(owners=user_obj) | Q(public=True))
        else:
            return qs.public()

    @staticmethod
    def view_study_results(user_obj, obj):
        return StudyPermissions.view_study_results_list(user_obj).contains(obj)

    @staticmethod
    def view_study_list(user_obj: User, qs: QuerySet[Study] | None = None) -> QuerySet[Study]:
        qs: QuerySet[Study] = qs if qs is not None else Study._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            # Owner of the study, it's public, or the user has been assigned a task from
            # the study.
            return qs.filter(
                Q(creator=user_obj)
                | Q(owners=user_obj)
                | Q(public=True)
                | Q(tasks__annotator=user_obj)
            )
        else:
            return qs.public()

    @staticmethod
    def view_study(user_obj, obj):
        return StudyPermissions.view_study_list(user_obj).contains(obj)


Study.perms_class = StudyPermissions


class StudyTaskSet(models.QuerySet):
    def pending(self):
        return self.filter(annotation=None)

    def for_user(self, user: User):
        return self.filter(annotator=user)

    def random_next(self):
        # This is really inefficient when performing on large sets of rows,
        # and getting a set of rows in a random order is pretty hard in SQL.
        # This should always be called once the studytask queryset has been
        # narrowed a lot.
        return self.order_by("?").first()


class StudyTask(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        unique_together = [["study", "annotator", "image"]]

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="tasks")
    # TODO: annotators might become M2M in the future
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    objects = StudyTaskSet.as_manager()

    @property
    def complete(self) -> bool:
        return hasattr(self, "annotation")


class StudyTaskPermissions:
    model = StudyTask
    perms = ["view_study_task"]
    filters = {"view_study_task": "view_study_task_list"}

    @staticmethod
    def view_study_task_list(
        user_obj: User, qs: QuerySet[StudyTask] | None = None
    ) -> QuerySet[StudyTask]:
        qs = qs if qs is not None else StudyTask._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            # Note: this allows people who can't see the image to see it if it's part of a study
            # task ONLY within the studytask check. In other words, they can't see it in the
            # gallery.
            return qs.filter(Q(annotator=user_obj) | Q(study__owners=user_obj))
        else:
            return qs.none()

    @staticmethod
    def view_study_task(user_obj, obj):
        return StudyTaskPermissions.view_study_task_list(user_obj).contains(obj)


StudyTask.perms_class = StudyTaskPermissions


class Annotation(TimeStampedModel):
    class Meta:
        constraints = [
            CheckConstraint(
                name="annotation_start_time_check", check=Q(start_time__lte=F("created"))
            ),
        ]
        unique_together = [["study", "task", "image", "annotator"]]

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="annotations")
    image = models.ForeignKey(Image, on_delete=models.PROTECT)
    task = models.OneToOneField(StudyTask, related_name="annotation", on_delete=models.RESTRICT)
    annotator = models.ForeignKey(User, on_delete=models.PROTECT)

    # For the ISIC GUI this time is generated on page load.
    # The created field acts as the end_time value.
    # This is nullable in the event that third party apps submit annotations, but
    # all annotations created by this app submit a start_time.
    start_time = models.DateTimeField(null=True)

    def get_absolute_url(self) -> str:
        return reverse("annotation-detail", args=[self.pk])

    @property
    def annotation_duration(self) -> Optional[timedelta]:
        if self.start_time:
            return self.created - self.start_time


class ResponseQuerySet(models.QuerySet):
    def for_display(self) -> list:
        for response in (
            self.annotate(
                value_answer=Cast(F("value"), CharField()),
                choice_answer=F("choice__text"),
                study_id=F("annotation__study__id"),
                study=F("annotation__study__name"),
                image=F("annotation__image__isic_id"),
                annotator=F("annotation__annotator__profile__hash_id"),
                annotation_duration=F("annotation__created") - F("annotation__start_time"),
                question_prompt=F("question__prompt"),
                answer=Case(
                    When(question__type=Question.QuestionType.SELECT, then=F("choice_answer")),
                    default=F("value_answer"),
                    output_field=CharField(),
                ),
            )
            .order_by("annotation__image__isic_id")
            .values(
                "study_id",
                "study",
                "image",
                "annotator",
                "annotation_duration",
                "question_prompt",
                "answer",
            )
            .iterator()
        ):
            if response["annotation_duration"] is None:
                annotation_duration = ""
            else:
                # formatting as total seconds is easier, otherwise long durations get printed as
                # 2 days, H:M:S.ms
                annotation_duration = response["annotation_duration"].total_seconds()

            yield {
                "study_id": response["study_id"],
                "study": response["study"],
                "image": response["image"],
                "annotator": response["annotator"],
                "annotation_duration": annotation_duration,
                "question": response["question_prompt"],
                "answer": response["answer"],
            }


class Response(TimeStampedModel):
    class Meta:
        unique_together = [["annotation", "question"]]
        constraints = [
            CheckConstraint(
                name="response_choice_or_value_check",
                check=Exact(
                    lhs=Func(
                        "choice",
                        "value",
                        function="num_nonnulls",
                        output_field=IntegerField(),
                    ),
                    rhs=Value(1),
                ),
            )
        ]

    objects = ResponseQuerySet.as_manager()
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="responses")
    # TODO: investigate limit_choices_to for admin capabilities
    # see: https://code.djangoproject.com/ticket/25306
    choice = models.ForeignKey(QuestionChoice, on_delete=models.CASCADE, null=True)
    # expect a single key inside named value. TODO: maybe add a constraint for this.
    value = models.JSONField(null=True)


class Markup(TimeStampedModel):
    class Meta:
        unique_together = [["annotation", "feature"]]

    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name="markups")
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT, related_name="markups")
    mask = S3FileField(upload_to=generate_upload_to)
    present = models.BooleanField()
