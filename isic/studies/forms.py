from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from isic.studies.models import Question, Response, Study


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
        questions: QuerySet[Question] = kwargs.pop("questions")
        self.questions = {x.pk: x for x in questions}

        num_diagnosis_questions = len(
            [question for question in questions if question.type == Question.QuestionType.DIAGNOSIS]
        )
        if num_diagnosis_questions > 1:
            # this is a hack because passing a per-question version of most frequent diagnoses is
            # unreasonably difficult.
            raise ValueError("Only one diagnosis question is allowed per study.")
        elif num_diagnosis_questions == 1:  # noqa: RET506
            # the study and user are necessary for diagnosis questions in order to compute
            # the most frequently used diagnosis.
            self.study = kwargs.pop("study")
            self.user = kwargs.pop("user")

            self.most_frequent_diagnoses = list(
                Response.objects.filter(
                    question=next(
                        question
                        for question in questions
                        if question.type == Question.QuestionType.DIAGNOSIS
                    ),
                    annotation__study=self.study,
                    annotation__annotator=self.user,
                )
                .values("choice", "choice__text")
                .alias(count=Count("choice"))
                .order_by("-count")
            )

        # remove study/user from kwargs before passing to super
        if "study" in kwargs:
            del kwargs["study"]

        if "user" in kwargs:
            del kwargs["user"]

        super().__init__(*args, **kwargs)
        for question in questions:
            # field names for django forms must be strings
            self.fields[str(question.pk)] = question.to_form_field(required=question.required)


class BaseStudyForm(forms.Form):
    fields = forms.fields_for_model(Study)

    name = fields["name"]
    description = fields["description"]
    attribution = fields["attribution"]
    collection = fields["collection"]
    public = fields["public"]

    def __init__(self, *args, **kwargs):
        collections = kwargs.pop("collections")
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["collection"].initial = collections

    annotators = forms.CharField()

    def clean_annotators(self) -> list[int]:
        value: str = self.cleaned_data["annotators"]
        values = {e.strip() for e in value.splitlines()}
        user_pks = set()

        for email_or_hash_id in values:
            user = User.objects.filter(
                Q(is_active=True) & Q(profile__hash_id__iexact=email_or_hash_id)
                | Q(emailaddress__email__iexact=email_or_hash_id)
            ).first()
            if not user:
                raise ValidationError(
                    f"Can't find any user with the identifier {email_or_hash_id}."
                )

            user_pks.add(user.pk)

        return list(user_pks)

    def clean_collection(self) -> bool:
        value = self.cleaned_data["collection"]

        if not self.user.has_perm("core.view_collection", value):
            raise ValidationError("You don't have access to create a study for that collection.")

        return value


class OfficialQuestionForm(forms.Form):
    question_id = forms.IntegerField(widget=forms.HiddenInput())
    required = forms.BooleanField(required=False)


class CustomQuestionForm(forms.Form):
    prompt = forms.CharField()
    choices = forms.CharField(
        help_text="A list of possible choices, one per line.", widget=forms.Textarea()
    )
    required = forms.BooleanField(required=False)

    def clean_choices(self) -> list[str]:
        value: str = self.cleaned_data["choices"]
        return [s.strip() for s in value.splitlines()]


class StudyEditForm(forms.Form):
    fields = forms.fields_for_model(Study)

    name = fields["name"]
    description = fields["description"]
