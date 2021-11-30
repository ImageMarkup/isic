from django import forms
from django.db.models.query import QuerySet

from isic.studies.models import QuestionChoice


class StudyTaskForm(forms.Form):
    """
    A dynamically generated form for a StudyTask.

    Takes an iterable of Question objects and creates fields named
    after the question id and have the proper field generated from
    Question.to_form_field.
    """

    def __init__(self, *args, **kwargs):
        questions: QuerySet[QuestionChoice] = kwargs.pop('questions')
        self.questions = {x.pk: x for x in questions}
        super().__init__(*args, **kwargs)
        for question in questions:
            # field names for django forms must be strings
            self.fields[str(question.pk)] = question.to_form_field
