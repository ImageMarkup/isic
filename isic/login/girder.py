import datetime
import random
import string
from typing import Optional

import bcrypt
from bson import ObjectId
from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.translation import gettext_noop as _
from pymongo import MongoClient

from isic.login.models import Profile


class GirderPasswordHasher(BasePasswordHasher):
    algorithm = 'bcrypt_girder'

    def verify(self, password: str, encoded: str) -> bool:
        return bcrypt.checkpw(
            password.encode('utf8'), encoded.replace('bcrypt_girder$', '').encode('utf8')
        )

    def encode(self, password, salt):
        # we shouldn't be encrypting passwords with Girder hasher
        raise NotImplementedError

    def safe_summary(self, encoded: str):
        return {
            _('algorithm'): self.algorithm,
            _('checksum'): mask_hash(encoded),
        }


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
                password=f'bcrypt_girder${girder_user["salt"]}',
                first_name=girder_user['firstName'],
                last_name=girder_user['lastName'],
                is_active=girder_user.get('status', 'enabled') == 'enabled',
                is_staff=girder_user['admin'],
                is_superuser=girder_user['admin'],
            )
        else:
            profile_changed = user.profile.sync_from_girder()
            if profile_changed:
                user.password = f'bcrypt_girder${user.profile.girder_salt}'
                user.profile.save()
                user.save()

        # TODO: consider overriding user_can_authenticate
        if user.profile.can_login():
            return super().authenticate(request, username, password, **kwargs)
