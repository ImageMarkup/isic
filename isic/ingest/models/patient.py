import secrets

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.constraints import CheckConstraint, UniqueConstraint
from django.db.models.query_utils import Q

from isic.core.constants import PATIENT_ID_REGEX


def _default_id():
    while True:
        patient_id = f"IP_{secrets.randbelow(9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the patient table
        if not Patient.objects.filter(id=patient_id).exists():
            return patient_id


class Patient(models.Model):
    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=10,
        validators=[RegexValidator(f"^{PATIENT_ID_REGEX}$")],
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="patients")
    private_patient_id = models.CharField(max_length=255)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_patient_id", "cohort"], name="unique_patient"),
            CheckConstraint(
                name="patient_id_valid_format",
                condition=Q(id__regex=f"^{PATIENT_ID_REGEX}$"),
            ),
        ]

    def __str__(self):
        return f"{self.private_patient_id}->{self.id}"
