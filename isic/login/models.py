import logging
from typing import Type

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from isic.login.girder import fetch_girder_user_by_email

logger = logging.getLogger(__name__)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    girder_id = models.CharField(
        max_length=24,
        unique=True,
        blank=True,
        null=True,
        validators=[RegexValidator(r'^[0-9a-f]{24}$')],
    )
    # this may be identical to user.password, but it needs to be retained to
    # check if the user password has changed.
    girder_salt = models.CharField(max_length=60, blank=True, null=True)
    email_verified = models.BooleanField(blank=True, null=True)

    def sync_from_girder(self) -> None:
        if not settings.ISIC_MONGO_URI:
            logger.warning('No ISIC_MONGO_URI configured; cannot sync from Girder.')
            return

        changed = False

        girder_user = fetch_girder_user_by_email(self.user.email)
        if not girder_user:
            raise Exception(f'Cannot retrieve girder_user for {self.user.email}.')

        if self.girder_id != str(girder_user['_id']):
            self.girder_id = str(girder_user['_id'])
            changed = True

        if self.user.is_active != (girder_user.get('status', 'enabled') == 'enabled'):
            self.user.is_active = girder_user.get('status', 'enabled') == 'enabled'
            changed = True

        if self.girder_salt != girder_user['salt']:
            self.girder_salt = girder_user['salt']
            if self.girder_salt is None:
                self.user.set_unusable_password()
            else:
                self.user.password = f'bcrypt_girder${self.girder_salt}'
            changed = True

        if self.email_verified != girder_user['emailVerified']:
            self.email_verified = girder_user['emailVerified']
            changed = True

        if changed:
            self.user.save()
            self.save()


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: Type[User], instance: User, created: bool, **kwargs):
    if created:
        profile = Profile(user=instance)
        profile.sync_from_girder()
