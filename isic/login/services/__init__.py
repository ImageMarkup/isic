from django.contrib.auth.models import User
from django.utils import timezone


def accept_terms(*, user: User) -> None:
    if user.profile.accepted_terms is None:
        user.profile.accepted_terms = timezone.now()
        user.profile.save(update_fields=["accepted_terms"])
