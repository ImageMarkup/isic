import logging
import secrets
import string

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Note: this unfortunately has to change in the CLI as well
# otherwise validation for a hash id would need it's own endpoint.
HASH_ID_REGEX = "^[A-HJ-NP-Z2-9]{5}$"

# A-Z0-9 except for O, 0, 1 and I.
# This alphabet allows for ~250k users before needing a 6th character
# Note: changing the alphabet necessitates changing HASH_ID_REGEX
HASH_ID_ALPHABET = list(set(string.ascii_uppercase + string.digits) - {"I", "1", "O", "0"})


def generate_random_hashid() -> str:
    while True:
        hash_id = "".join(secrets.choice(HASH_ID_ALPHABET) for _ in range(5))
        if not Profile.objects.filter(hash_id=hash_id).exists():
            return hash_id


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    hash_id = models.CharField(
        max_length=5,
        unique=True,
        # A-Z0-9 except for O, 0, 1 and I.
        validators=[RegexValidator(HASH_ID_REGEX)],
    )
    accepted_terms = models.DateTimeField(null=True)

    def __str__(self) -> str:
        return self.user.username


@receiver(post_save, sender=User)
def create_or_save_user_profile(
    sender: type[User],
    instance: User,
    created: bool,  # noqa: FBT001
    **kwargs,
):
    if created:
        Profile.objects.create(user=instance, hash_id=generate_random_hashid())
