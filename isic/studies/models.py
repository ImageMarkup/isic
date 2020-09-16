from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django_extensions.db.models import TimeStampedModel


class DeferredFieldsManager(models.Manager):
    def __init__(self, *deferred_fields):
        self.deferred_fields = deferred_fields
        super().__init__()

    def get_queryset(self):
        return super().get_queryset().defer(*self.deferred_fields)


class Image(TimeStampedModel):
    object_id = models.CharField(unique=True, max_length=24)


class Question(TimeStampedModel):
    class Meta:
        ordering = ['prompt']

    SELECT = 'select'
    TYPE_CHOICES = [(SELECT, 'Select')]
    required = models.BooleanField(default=True)
    prompt = models.CharField(max_length=400, unique=True)
    type = models.CharField(max_length=6, choices=TYPE_CHOICES, default=SELECT)
    official = models.BooleanField()
    # TODO: maybe add a default field

    def __str__(self):
        return self.prompt


class QuestionChoice(TimeStampedModel):
    question = models.ForeignKey(Question, related_name='choices', on_delete=models.CASCADE)
    text = models.CharField(max_length=100)

    def __str__(self):
        return self.text


class Feature(TimeStampedModel):
    class Meta:
        ordering = ['name']

    required = models.BooleanField(default=False)
    name = ArrayField(models.CharField(max_length=200))
    official = models.BooleanField()

    @property
    def label(self):
        return ' : '.join(self.name)

    def __str__(self):
        return self.label


class Study(TimeStampedModel):
    class Meta:
        verbose_name_plural = 'Studies'

    creator = models.ForeignKey(User, on_delete=models.CASCADE)

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()

    features = models.ManyToManyField(Feature)
    questions = models.ManyToManyField(Question)

    def __str__(self):
        return self.name


class StudyTask(TimeStampedModel):
    class Meta:
        unique_together = [['study', 'annotator', 'image']]

    study = models.ForeignKey(Study, on_delete=models.PROTECT, related_name='tasks')
    # TODO: annotators might become M2M in the future
    annotator = models.ForeignKey(User, on_delete=models.PROTECT)
    image = models.ForeignKey(Image, on_delete=models.PROTECT)

    @property
    def complete(self):
        return hasattr(self, 'annotation')


class Annotation(TimeStampedModel):
    study = models.ForeignKey(Study, on_delete=models.CASCADE)
    image = models.ForeignKey(Image, on_delete=models.PROTECT)
    task = models.OneToOneField(StudyTask, related_name='annotation', on_delete=models.CASCADE)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE)

    # TODO: auditing/telemetry start/stop times, logs, etc


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
