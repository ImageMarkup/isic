import random

from django.core.validators import RegexValidator
from django.db import IntegrityError, models
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from isic.core.constants import ISIC_ID_REGEX


def _default_id():
    while True:
        isic_id = f'ISIC_{random.randint(0, 9999999):07}'
        # This has a race condition, so the actual creation should be retried
        if not IsicId.objects.filter(id=isic_id).exists():
            return isic_id


class IsicId(models.Model):
    id = models.CharField(
        primary_key=True,
        default=_default_id,
        verbose_name='ISIC ID',
        max_length=12,
        validators=[RegexValidator(f'^{ISIC_ID_REGEX}$')],
    )

    def __str__(self) -> str:
        return self.id

    @classmethod
    @retry(reraise=True, retry=retry_if_exception_type(IntegrityError), stop=stop_after_attempt(10))
    def safe_create(cls):
        """Safely create an IsicId, without race conditions."""
        return cls.objects.create()
