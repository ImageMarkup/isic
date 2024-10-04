import secrets

from django.core.validators import RegexValidator
from django.db import IntegrityError, models

from isic.core.constants import ISIC_ID_REGEX


class IsicIdManager(models.Manager):
    def create_random(self):
        """
        Create a random unused ISIC ID.

        Note that this is prone to race conditions. The actual creation should be wrapped
        in a call to lock_table_for_writes(IsicId).
        """
        obj = None
        for _ in range(10):
            isic_id = f"ISIC_{secrets.randbelow(9999999):07}"
            if not self.filter(pk=isic_id).exists():
                obj = self.create(pk=isic_id)
                break

        if obj is None:
            raise IntegrityError("Failed to create a unique ISIC ID")

        return obj


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
