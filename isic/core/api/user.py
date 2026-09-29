from datetime import datetime

from django.contrib.auth.models import User
from ninja import Field, ModelSchema, Router

from isic.auth import is_authenticated
from isic.login.services import accept_terms
from isic.types import AuthenticatedHttpRequest

router = Router()


class UserOut(ModelSchema):
    class Meta:
        model = User
        fields = [
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
    "/me/",
    summary="Retrieve the currently logged in user.",
    response=UserOut,
    include_in_schema=True,
    auth=is_authenticated,
)
def user_me(request: AuthenticatedHttpRequest):
    return request.user


@router.put("/accept-terms/", include_in_schema=False, auth=is_authenticated)
def user_accept_terms(request: AuthenticatedHttpRequest):
    accept_terms(user=request.user)

    return {}
