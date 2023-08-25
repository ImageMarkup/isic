import random

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.query_utils import Q

from isic.core.constants import LESION_ID_REGEX


def _default_id():
    while True:
        lesion_id = f"IL_{random.randint(0, 9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the Lesion table
        if not Lesion.objects.filter(id=lesion_id).exists():
            return lesion_id


class Lesion(models.Model):
    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_lesion_id", "cohort"], name="unique_lesion"),
            CheckConstraint(
                name="lesion_id_valid_format",
                check=Q(id__regex=f"^{LESION_ID_REGEX}$"),
            ),
        ]

    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=12,
        validators=[RegexValidator(f"^{LESION_ID_REGEX}$")],
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="lesions")
    private_lesion_id = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.private_lesion_id}->{self.id}"
