from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.constraints import UniqueConstraint
from django.db.models.query_utils import Q
from django.forms.fields import CharField as FormCharField
from django.forms.fields import ChoiceField
from django.forms.widgets import RadioSelect
from django_extensions.db.models import TimeStampedModel

from isic.studies.widgets import DiagnosisPicker


class Question(TimeStampedModel):
    class QuestionType(models.TextChoices):
        SELECT = "select", "Select"
        NUMBER = "number", "Number"
        DIAGNOSIS = "diagnosis", "Diagnosis"

    prompt = models.CharField(max_length=400)
    type = models.CharField(max_length=9, choices=QuestionType.choices, default=QuestionType.SELECT)
    official = models.BooleanField()
    # TODO: maybe add a default field

    class Meta(TimeStampedModel.Meta):
        ordering = ["prompt"]
        constraints = [
            UniqueConstraint(
                name="question_official_prompt_unique",
                fields=["prompt"],
                condition=Q(official=True),
            )
        ]

    def __str__(self) -> str:
        return self.prompt

    def to_form_field(self, *, required: bool) -> ChoiceField | FormCharField:
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
        elif self.type == self.QuestionType.DIAGNOSIS:
            return ChoiceField(
                required=required,
                choices=[(choice.pk, choice.text) for choice in self.choices.all()],
                label=self.prompt,
                widget=DiagnosisPicker,
            )
        else:
            raise ValueError(f"Unknown question type: {self.type}")

    def choices_for_display(self):
        if self.type == self.QuestionType.DIAGNOSIS:
            return [f"All {self.choices.count()} diagnoses"]
        elif self.type == self.QuestionType.SELECT:
            return [choice.text for choice in self.choices.all()]
        elif self.type == self.QuestionType.NUMBER:
            return ["Numeric"]
        else:
            raise ValueError(f"Unknown question type: {self.type}")

    def save(self, **kwargs):
        if self.pk and self.study_set.filter(annotations__isnull=False).exists():
            raise ValidationError("Can't modify the question, it has already been answered.")

        return super().save(**kwargs)
