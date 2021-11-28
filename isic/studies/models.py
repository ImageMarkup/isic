from typing import Optional

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from django.urls import reverse
from django_extensions.db.models import TimeStampedModel
from girder_utils.db import DeferredFieldsManager

from isic.core.models import Image


class Question(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        ordering = ['prompt']

    class QuestionType(models.TextChoices):
        SELECT = 'select', 'Select'

    required = models.BooleanField(default=True)
    prompt = models.CharField(max_length=400, unique=True)
    type = models.CharField(max_length=6, choices=QuestionType.choices, default=QuestionType.SELECT)
    official = models.BooleanField()
    # TODO: maybe add a default field

    def __str__(self) -> str:
        return self.prompt

    @property
    def to_form_field(self):
        return ChoiceField(
            required=self.required,
            choices=[(choice.pk, choice.text) for choice in self.choices.all()],
            label=self.prompt,
            widget=RadioSelect,
        )


class QuestionChoice(TimeStampedModel):
    question = models.ForeignKey(Question, related_name='choices', on_delete=models.CASCADE)
    text = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.text


class Feature(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        ordering = ['name']

    required = models.BooleanField(default=False)
    name = ArrayField(models.CharField(max_length=200))
    official = models.BooleanField()

    @property
    def label(self) -> str:
        return ' : '.join(self.name)

    def __str__(self) -> str:
        return self.label


class Study(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        verbose_name_plural = 'Studies'

    creator = models.ForeignKey(User, on_delete=models.PROTECT)

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    features = models.ManyToManyField(Feature)
    questions = models.ManyToManyField(Question)

    # public study means that all images in the study must be public
    # and all of the related data to the study is public (responses).
    # if a study is private, only the owner can see the responses of
    # a study.
    public = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse('study-detail', args=[self.pk])


class StudyPermissions:
    model = Study
    perms = ['view_study']
    filters = {'view_study': 'view_study_list'}

    @staticmethod
    def view_study_list(user_obj: User, qs: Optional[QuerySet[Study]] = None) -> QuerySet[Study]:
        qs: QuerySet[Study] = qs if qs is not None else Study._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            # Creator of the study, it's public, or the user has been assigned a task from
            # the study.
            return qs.filter(Q(creator=user_obj) | Q(public=True) | Q(tasks__annotator=user_obj))
        else:
            return qs.filter(public=True)

    @staticmethod
    def view_study(user_obj, obj):
        # TODO: use .contains in django 4
        return StudyPermissions.view_study_list(user_obj).filter(pk=obj.pk).exists()


Study.perms_class = StudyPermissions


class StudyTaskSet(models.QuerySet):
    def pending(self):
        return self.filter(annotation=None)

    def for_user(self, user: User):
        return self.filter(annotator=user)


class StudyTask(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        unique_together = [['study', 'annotator', 'image']]

    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='tasks')
    # TODO: annotators might become M2M in the future
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.CASCADE)

    objects = StudyTaskSet.as_manager()

    @property
    def complete(self) -> bool:
        return hasattr(self, 'annotation')


class StudyTaskPermissions:
    model = StudyTask
    perms = ['view_study_task']
    filters = {'view_study_task': 'view_study_task_list'}

    @staticmethod
    def view_study_task_list(
        user_obj: User, qs: Optional[QuerySet[StudyTask]] = None
    ) -> QuerySet[StudyTask]:
        qs = qs if qs is not None else StudyTask._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            # Note: this allows people who can't see the image to see it if it's part of a study
            # task ONLY within the studytask check. In other words, they can't see it in the
            # gallery.
            return qs.filter(Q(annotator=user_obj) | Q(study__creator=user_obj))
        else:
            return qs.none()

    @staticmethod
    def view_study_task(user_obj, obj):
        # TODO: use .contains in django 4
        return StudyTaskPermissions.view_study_task_list(user_obj).filter(pk=obj.pk).exists()


StudyTask.perms_class = StudyTaskPermissions


class Annotation(TimeStampedModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name='annotations')
    image = models.ForeignKey(Image, on_delete=models.PROTECT)
    task = models.OneToOneField(StudyTask, related_name='annotation', on_delete=models.RESTRICT)
    annotator = models.ForeignKey(User, on_delete=models.PROTECT)

    # TODO: auditing/telemetry start/stop times, logs, etc

    def get_absolute_url(self) -> str:
        return reverse('annotation-detail', args=[self.pk])


class AnnotationPermissions:
    model = Annotation
    perms = ['view_annotation']
    filters = {'view_annotation': 'view_annotation_list'}

    @staticmethod
    def view_annotation_list(
        user_obj: User, qs: Optional[QuerySet[Annotation]] = None
    ) -> QuerySet[Annotation]:
        qs = qs if qs is not None else Annotation._default_manager.all()

        if user_obj.is_staff:
            return qs
        elif user_obj.is_authenticated:
            # Note: this allows people who can't see the image to see it if it's part of an
            # annotation. This is similar to StudyTaskPermissions
            return qs.filter(Q(annotator=user_obj) | Q(study__creator=user_obj))
        else:
            return qs.none()

    @staticmethod
    def view_annotation(user_obj, obj):
        # TODO: use .contains in django 4
        return AnnotationPermissions.view_annotation_list(user_obj).filter(pk=obj.pk).exists()


Annotation.perms_class = AnnotationPermissions


class Response(TimeStampedModel):
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    # TODO: investigate limit_choices_to for admin capabilities
    # see: https://code.djangoproject.com/ticket/25306
    choice = models.ForeignKey(QuestionChoice, on_delete=models.CASCADE)


class Markup(TimeStampedModel):
    annotation = models.ForeignKey(Annotation, on_delete=models.CASCADE, related_name='markups')
    feature = models.ForeignKey(Feature, on_delete=models.PROTECT, related_name='markups')
    mask = models.BinaryField()
    present = models.BooleanField()

    objects = DeferredFieldsManager('mask')
