import datetime
import random
import string
from typing import Optional

from bson import ObjectId
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from pymongo import MongoClient

from isic.login.models import Profile


def create_girder_token(girder_user_id: str) -> str:
    db = MongoClient(settings.ISIC_MONGO_URI).get_database()
    now = datetime.datetime.utcnow()
    token_value = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(64))
    db['token'].insert_one(
        {
            '_id': token_value,
            'userId': ObjectId(girder_user_id),
            'created': now,
            'expires': now + datetime.timedelta(days=30.0),
            'scope': ['core.user_auth'],
            'access': {
                'groups': [],
                'users': [{'id': ObjectId(girder_user_id), 'level': 2, 'flags': []}],
            },
        }
    )
    return token_value


class GirderBackend(ModelBackend):
    def authenticate(
        self, request: Optional[HttpRequest], username: str = None, password: str = None, **kwargs
    ) -> Optional[User]:
        # let the django auth backend deal with non-girder users and existing users that
        # have a usable password
        existing_user = User.objects.get(username=username)
        if not existing_user or existing_user.has_usable_password():
            return None

        girder_user = Profile.fetch_girder_user(username)
        if not girder_user:
            return None

        try:
            user = User.objects.get(username=girder_user['email'])
        except User.DoesNotExist:
            user = User.objects.create(
                date_joined=girder_user['created'].replace(tzinfo=datetime.timezone.utc),
                username=girder_user['email'],
                email=girder_user['email'],
                first_name=girder_user['firstName'],
                last_name=girder_user['lastName'],
                is_active=girder_user.get('status', 'enabled') == 'enabled',
                is_staff=girder_user['admin'],
                is_superuser=girder_user['admin'],
            )
        else:
            profile_changed = user.profile.sync_from_girder()
            if profile_changed:
                user.profile.save()

        try:
            user.profile.validate_girder_password(password)
        except ValidationError:
            return None

        if not user.check_password(password):
            user.set_password(password)  # Note this makes the user have a 'usable' password
            user.save()

        return user
