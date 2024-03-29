from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.db.models.query_utils import Q

from isic.studies.models import Question, Study


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
