import logging
import string

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from hashids import Hashids

from isic.core.constants import MONGO_ID_REGEX

logger = logging.getLogger(__name__)


def get_hashid_hasher():
    # This alphabet allows for ~250k users before needing a 6th character
    return Hashids(
        min_length=5,
        alphabet=list(set(string.ascii_uppercase + string.digits) - {'I', '1', 'O', '0'}),
    )


def get_hashid(value: int) -> str:
    return get_hashid_hasher().encode(value)


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
    hash_id = models.CharField(
        max_length=5,
        unique=True,
        # A-Z0-9 except for O, 0, 1 and I.
        validators=[RegexValidator('^[A-HJ-NP-Z2-9]{5}')],
    )
    accepted_terms = models.DateTimeField(null=True)


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender: type[User], instance: User, created: bool, **kwargs):
    if created:
        Profile.objects.create(user=instance, hash_id=get_hashid(instance.pk))
