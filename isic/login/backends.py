import datetime
import logging
from typing import Optional

from allauth.account.auth_backends import AuthenticationBackend
import bcrypt
from django.conf import settings
from django.contrib.auth.hashers import BasePasswordHasher, mask_hash
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.utils.translation import gettext_noop as _

from isic.login.girder import fetch_girder_user_by_email

logger = logging.getLogger(__name__)


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


class GirderBackend(AuthenticationBackend):
    def authenticate(self, request: Optional[HttpRequest], **credentials) -> Optional[User]:
        if not settings.ISIC_MONGO_URI:
            logger.warning('No ISIC_MONGO_URI configured; cannot authenticate from Girder.')
            return None

        email = credentials.get('email', credentials.get('username'))
        if not email:
            return None

        girder_user = fetch_girder_user_by_email(email)
        if not girder_user:
            return None

        self.get_or_create_user_from_girder(girder_user)

        return super().authenticate(request, **credentials)

    @staticmethod
    def get_or_create_user_from_girder(girder_user: dict) -> User:
        try:
            user = User.objects.get(username=girder_user['email'])
        except User.DoesNotExist:
            user = User(
                date_joined=girder_user['created'].replace(tzinfo=datetime.timezone.utc),
                username=girder_user['email'],
                email=girder_user['email'],
                first_name=girder_user['firstName'],
                last_name=girder_user['lastName'],
                is_active=girder_user.get('status', 'enabled') == 'enabled',
                is_staff=girder_user['admin'],
                is_superuser=girder_user['admin'],
            )
            if girder_user['salt'] is None:
                user.set_unusable_password()
            else:
                user.password = (f'bcrypt_girder${girder_user["salt"]}',)
            user.save()
        else:
            user.profile.sync_from_girder()

        return user
