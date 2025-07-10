from django.core.exceptions import ValidationError
from django.db import models
from django_extensions.db.models import TimeStampedModel

from .question import Question


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
            and Question.objects.filter(
                pk=self.question_id, study__annotations__isnull=False
            ).exists()
        ):
            raise ValidationError(
                "Can't modify the choice, the question has already been answered."
            )

        return super().save(**kwargs)
