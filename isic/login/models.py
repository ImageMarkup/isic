from django.db import models
from django.conf import settings
from oauth2_provider.models import AccessToken
import random
from typing import Dict
import string
from pymongo.mongo_client import MongoClient
import datetime

from isic.login.girder import get_girder_user

class GirderOAuthAccessToken(AccessToken):
    girder_token = models.CharField(max_length=64)

    @staticmethod
    def _create_girder_token(girder_user: Dict) -> str:
        db = MongoClient(settings.ARCHIVE_MONGO_URI).girder
        now = datetime.datetime.utcnow()
        token_value = ''.join(
            random.choice(string.ascii_letters + string.digits) for _ in range(64)
        )
        db['token'].insert_one(
            {
                '_id': token_value,
                'created': now,
                'expires': now + datetime.timedelta(days=30.0),
                'scope': ('core.user_auth',),
            }
        )
        return token_value

    def save(self, *args, **kwargs):
        self.girder_token = self._create_girder_token(get_girder_user(self.user.email))
        super().save(*args, **kwargs)
