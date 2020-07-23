from typing import Dict, Optional, Type

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from passlib.hash import bcrypt
from pymongo import MongoClient
from pymongo.collection import Collection


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    girder_id = models.CharField(
        max_length=24,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    girder_salt = models.CharField(max_length=60, blank=True, null=True)
    email_verified = models.BooleanField(blank=True, null=True)

    def sync_from_girder(self):
        changed = False

        girder_user = self.fetch_girder_user(self.user.email)
        if not girder_user:
            raise Exception(f'Cannot retrieve girder_user for {self.user.email}.')

        if self.girder_id != str(girder_user['_id']):
            self.girder_id = str(girder_user['_id'])
            changed = True

        if self.girder_salt != girder_user['salt']:
            self.girder_salt = girder_user['salt']
            changed = True

        if self.email_verified != girder_user['emailVerified']:
            self.email_verified = girder_user['emailVerified']
            changed = True

        return changed

    def validate_girder_password(self, password: str) -> None:
        # Handle users with no password
        if not self.girder_salt:
            raise ValidationError(
                'This user does not have a password. You must reset your password to obtain one.'
            )

        # Verify password
        if not bcrypt.verify(password, self.girder_salt):
            raise ValidationError('Login failed.')

        if not self.user.is_active:
            raise ValidationError('Account is disabled.')

    @classmethod
    def _girder_db(cls) -> Collection:
        # Default database name is specified within ISIC_MONGO_URI
        return MongoClient(settings.ISIC_MONGO_URI).get_database()

    @classmethod
    def fetch_girder_user(cls, email: str) -> Optional[Dict]:
        return cls._girder_db()['user'].find_one({'email': email.lower()})


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: Type[User], instance: User, created: bool, **kwargs):
    if created:
        profile = Profile(user=instance)
        profile.sync_from_girder()
        profile.save()
