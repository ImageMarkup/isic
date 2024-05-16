import secrets

from django.db import models
from django.db.models.constraints import UniqueConstraint


def _default_id():
    while True:
        rcm_case_id = f"{secrets.randbelow(9999999):07}"
        # This has a race condition, so the actual creation should be retried or wrapped
        # in a select for update on the rcm_case table
        if not RcmCase.objects.filter(id=rcm_case_id).exists():
            return rcm_case_id


class RcmCase(models.Model):
    id = models.CharField(
        primary_key=True,
        default=_default_id,
        max_length=7,
    )
    cohort = models.ForeignKey("Cohort", on_delete=models.CASCADE, related_name="rcm_cases")
    private_rcm_case_id = models.CharField(max_length=255)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["private_rcm_case_id", "cohort"], name="unique_rcm_case"),
        ]

    def __str__(self):
        return f"{self.private_rcm_case_id}->{self.id}"
