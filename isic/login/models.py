import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from isic.core import MONGO_ID_REGEX
from isic.login.girder import fetch_girder_user_by_email

logger = logging.getLogger(__name__)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    girder_id = models.CharField(
        max_length=24,
        unique=True,
        blank=True,
        # Make this nullable to allow a uniqueness constraint
        null=True,
        validators=[RegexValidator(f'^{MONGO_ID_REGEX}$')],
    )
    # this may be identical to user.password, but it needs to be retained to
    # check if the user password has changed.
    girder_salt = models.CharField(max_length=60, blank=True)

    def sync_from_girder(self) -> None:
        girder_user = fetch_girder_user_by_email(self.user.email)
        if not girder_user:
            # If this is a Django-native signup, the girder_user will not have been created yet
            logger.info(f'Cannot retrieve girder_user for {self.user.email}.')
            return

        changed = False

        if self.girder_id != str(girder_user['_id']):
            self.girder_id = str(girder_user['_id'])
            changed = True

        if self.user.is_active != (girder_user.get('status', 'enabled') == 'enabled'):
            self.user.is_active = girder_user.get('status', 'enabled') == 'enabled'
            changed = True

        if self.girder_salt != girder_user['salt']:
            # An empty salt is stored as None in MongoDB, but should be '' here
            self.girder_salt = girder_user['salt'] or ''
            if not self.girder_salt:
                self.user.set_unusable_password()
            else:
                self.user.password = f'bcrypt_girder${self.girder_salt}'
            changed = True

        if changed:
            self.user.save()
            self.save()


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: type[User], instance: User, created: bool, **kwargs):
    if created:
        profile = Profile.objects.create(user=instance)
        if settings.ISIC_MONGO_URI:
            profile.sync_from_girder()
