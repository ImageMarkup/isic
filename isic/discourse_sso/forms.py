from typing import Dict, List, Optional

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from passlib.context import CryptContext
from pymongo import MongoClient


class DiscourseSSOLoginForm(forms.Form):
    login = forms.CharField(label='Email or username', max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)

    girder_user: Optional[Dict] = None
    girder_user_groups: Optional[List[Dict]] = None

    @staticmethod
    def _get_girder_user(login) -> Optional[Dict]:
        login_field = 'email' if '@' in login else 'login'
        db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
        return db.users.find_one({login_field: login})

    @staticmethod
    def _get_girder_user_groups(user: Dict) -> List:
        db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
        return list(db.groups.find({'$id': {'$in': user.get('groups', [])}}))

    def clean_login(self):
        return self.cleaned_data['login'].lower()

    def clean(self):
        # TODO: Support OTP
        # TODO: Support email verification requirement
        cleaned_data = super().clean()
        login, password = cleaned_data['login'], cleaned_data['password']

        self.girder_user = self._get_girder_user(login)
        if self.girder_user is None:
            raise ValidationError('Login failed.')

        self.girder_user_groups = self._get_girder_user_groups(self.girder_user)

        # Handle users with no password
        if not self.girder_user['salt']:
            raise ValidationError(
                'This user does not have a password. ' 'You must reset your password to obtain one.'
            )

        # Verify password
        if not CryptContext(schemes=['bcrypt']).verify(password, self.girder_user['salt']):
            raise ValidationError('Login failed.')

        if self.girder_user.get('status', 'enabled') == 'disabled':
            raise ValidationError('Account is disabled.')
