from datetime import datetime

from django.contrib.auth.models import User
from django.http.request import HttpRequest
from django.utils import timezone
from ninja import Field, ModelSchema, Router
from ninja.security import django_auth

router = Router()


class UserOut(ModelSchema):
    class Config:
        model = User
        model_fields = [
            "id",
            "email",
            "first_name",
            "last_name",
        ]

    created: datetime = Field(alias="date_joined")
    accepted_terms: datetime | None = Field(alias="profile.accepted_terms")
    hash_id: str | None = Field(alias="profile.hash_id")
    full_name: str

    @staticmethod
    def resolve_full_name(obj: User):
        return f"{obj.first_name} {obj.last_name}"


@router.get(
    "/me/", summary="Retrieve the currently logged in user.", response=UserOut, auth=django_auth
)
def user_me(request: HttpRequest):
    return request.user


@router.put("/accept-terms/", include_in_schema=False, auth=django_auth)
def accept_terms_of_use(request: HttpRequest):
    if not request.user.profile.accepted_terms:
        request.user.profile.accepted_terms = timezone.now()
        request.user.profile.save(update_fields=["accepted_terms"])

    return {}
