from collections.abc import Generator
from typing import Any

from django.db import models
from django.db.models import Case, CharField, Value, When
from django.db.models.constraints import CheckConstraint
from django.db.models.expressions import F, Func
from django.db.models.fields import IntegerField
from django.db.models.functions import Cast
from django.db.models.lookups import Exact
from django_extensions.db.models import TimeStampedModel

from .annotation import Annotation
from .question import Question
from .question_choice import QuestionChoice


class ResponseQuerySet(models.QuerySet):
    def for_display(self) -> Generator[dict[str, Any]]:
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
                    When(
                        question__type__in=[
                            Question.QuestionType.SELECT,
                            Question.QuestionType.DIAGNOSIS,
                        ],
                        then=F("choice_answer"),
                    ),
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
                condition=Exact(
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
