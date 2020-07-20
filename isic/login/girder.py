from typing import Dict, List, Optional

from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from passlib.hash import bcrypt
from pymongo import MongoClient


def get_girder_user(email: str) -> Optional[Dict]:
    # Default database name is specified within ARCHIVE_MONGO_URI
    db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
    # To facilitate type checking, use dictionary-style collection lookup
    return db['user'].find_one({'email': email})


def validate_girder_password(girder_user: Dict, password: str) -> None:
    # Handle users with no password
    if not girder_user['salt']:
        raise ValidationError(
            'This user does not have a password. ' 'You must reset your password to obtain one.'
        )

    # Verify password
    if not bcrypt.verify(password, girder_user['salt']):
        raise ValidationError('Login failed.')

    if girder_user.get('status', 'enabled') == 'disabled':
        raise ValidationError('Account is disabled.')


def get_girder_user_groups(girder_user: Dict) -> List:
    db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
    return list(db.groups.find({'$id': {'$in': girder_user.get('groups', [])}}))


class GirderBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None):
        girder_user = get_girder_user(username)

        if not girder_user:
            return None

        try:
            validate_girder_password(girder_user, password)
        except Exception:
            return None

        try:
            user = User.objects.get(username=girder_user['email'])
        except User.DoesNotExist:
            user = User.objects.create(
                date_joined=girder_user['created'],
                username=girder_user['email'],
                email=girder_user['email'],
                password=make_password(password),
                first_name=girder_user['firstName'],
                last_name=girder_user['lastName'],
                is_staff=girder_user['admin'],
                is_superuser=girder_user['admin'],
            )

        return user

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
