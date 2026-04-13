from django.db import models

from .question import Question
from .study import Study


class StudyQuestion(models.Model):
    study = models.ForeignKey(Study, on_delete=models.CASCADE, related_name="study_questions")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="study_questions")
    order = models.PositiveSmallIntegerField(default=0)
    required = models.BooleanField()

    class Meta:
        unique_together = [["study", "question"]]

    def __str__(self) -> str:
        return f"{self.pk}"
