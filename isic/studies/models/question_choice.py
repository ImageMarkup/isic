from django.core.exceptions import ValidationError
from django.db import models
from django_extensions.db.models import TimeStampedModel

from .annotation import Annotation
from .question import Question
from .study import Study


class QuestionChoice(TimeStampedModel):
    class Meta(TimeStampedModel.Meta):
        unique_together = [["question", "text"]]

    question = models.ForeignKey(Question, related_name="choices", on_delete=models.CASCADE)
    text = models.CharField(max_length=255)

    def __str__(self) -> str:
        return self.text

    def save(self, **kwargs):
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
