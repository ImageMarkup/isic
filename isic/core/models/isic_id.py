import secrets

from django.core.validators import RegexValidator
from django.db import IntegrityError, models
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from isic.core.constants import ISIC_ID_REGEX


class IsicIdManager(models.Manager):
    @retry(
        reraise=True,
        retry=retry_if_exception_type(IntegrityError),
        stop=stop_after_attempt(10),
    )
    def create_random(self):
        return self.create(id=f"ISIC_{secrets.randbelow(9999999):07}")


class IsicId(models.Model):
    id = models.CharField(
        primary_key=True,
        verbose_name="ISIC ID",
        max_length=12,
        validators=[RegexValidator(f"^{ISIC_ID_REGEX}$")],
    )

    objects = IsicIdManager()

    def __str__(self) -> str:
        return self.id
