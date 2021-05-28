import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
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

    def sync_from_girder(self) -> bool:
        if not settings.ISIC_MONGO_URI:
            logger.warning('No ISIC_MONGO_URI configured; cannot sync from Girder.')
            return False

        changed = False

        girder_user = fetch_girder_user_by_email(self.user.email)
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

    def can_login(self) -> bool:
        # Handle users with no password
        if not self.girder_salt:
            raise ValidationError(
                'This user does not have a password. You must reset your password to obtain one.'
            )

        if not self.user.is_active:
            raise ValidationError('Account is disabled.')

        return True


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: type[User], instance: User, created: bool, **kwargs):
    if created:
        profile = Profile(user=instance)
        profile.sync_from_girder()
        profile.save()
