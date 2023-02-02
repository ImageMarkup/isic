from django import forms
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _


class RealNameSignupForm(forms.Form):
    """
    An Allauth signup form which requests a user's real name.

    The import path of this class should be set as the setting ACCOUNT_SIGNUP_FORM_CLASS.
    """

    first_name = forms.CharField(
        max_length=150,
        label=_("First name"),
        widget=forms.TextInput(
            attrs={"placeholder": _("First name"), "autocomplete": "given-name"}
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        label=_("Last name"),
        widget=forms.TextInput(
            attrs={"placeholder": _("Last name"), "auto complete": "family-name"}
        ),
    )

    field_order = [
        # fields are ignored when not present
        "first_name",
        "last_name",
        "email",
        "email2",
        "username",
        "password1",
        "password2",
    ]

    def signup(self, request: HttpRequest, user: User):
        # Allauth requires this method to be defined
        pass
