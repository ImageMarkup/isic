from django import forms
from allauth.account.models import EmailAddress
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.query import QuerySet

from isic.studies.models import Question


class StudyTaskForm(forms.Form):
    """
    A dynamically generated form for a StudyTask.

    Takes an iterable of Question objects and creates fields named
    after the question id and have the proper field generated from
    Question.to_form_field.
    """

    start_time = forms.DateTimeField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        # Note: questions must be annotated with a required attribute
        questions: QuerySet[Question] = kwargs.pop('questions')
        self.questions = {x.pk: x for x in questions}
        super().__init__(*args, **kwargs)
        for question in questions:
            # field names for django forms must be strings
            self.fields[str(question.pk)] = question.to_form_field(question.required)
