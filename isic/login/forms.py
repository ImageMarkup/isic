from django import forms
from django.contrib.auth.forms import AuthenticationForm, UsernameField


class LoginForm(AuthenticationForm):
    username = UsernameField(
        label='Email', widget=forms.TextInput(attrs={'autofocus': True, 'autocomplete': 'username'})
    )
