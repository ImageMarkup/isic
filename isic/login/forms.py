from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from isic.login.girder import create_girder_user


class RealNameSignupForm(forms.Form):
    """
    An Allauth signup form which requests a user's real name.

    The import path of this class should be set as the setting ACCOUNT_SIGNUP_FORM_CLASS.
    """

    first_name = forms.CharField(
        max_length=150,
        label=_('First name'),
        widget=forms.TextInput(
            attrs={'placeholder': _('First name'), 'autocomplete': 'given-name'}
        ),
    )
    last_name = forms.CharField(
        max_length=150,
        label=_('Last name'),
        widget=forms.TextInput(
            attrs={'placeholder': _('Last name'), 'auto complete': 'family-name'}
        ),
    )

    field_order = [
        # fields are ignored when not present
        'first_name',
        'last_name',
        'email',
        'email2',
        'username',
        'password1',
        'password2',
    ]

    def signup(self, request: HttpRequest, user: User):
        # Allauth requires this method to be defined

        # It would be more semantically appropriate to do this on the
        # allauth.account.signals.user_signed_up signal, but the raw password from the form is
        # necessary
        if not settings.ISIC_MONGO_URI:
            create_girder_user(
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                password=self.cleaned_data['password1'],
            )
