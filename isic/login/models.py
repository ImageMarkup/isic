import logging

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from isic.core.constants import MONGO_ID_REGEX

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


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: type[User], instance: User, created: bool, **kwargs):
    if created:
        Profile.objects.create(user=instance)
