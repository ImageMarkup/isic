from collections.abc import Callable
from typing import Literal

from django.http import HttpRequest
from ninja.security import django_auth

from isic.core.permissions import SessionAuthStaffUser

ACCESS_PERMS = ["any", "is_authenticated", "is_staff"]

from allauth.idp.oidc.contrib.ninja.security import TokenAuth  # noqa: E402


class PermissionedTokenAuth(TokenAuth):
    def __init__(
        self, permission: Literal["any", "is_authenticated", "is_staff"], scope: str | list | dict
    ):
        if permission not in ACCESS_PERMS:
            raise ValueError(f"Invalid permission: {permission}")

        super().__init__(scope)
        self.permission = permission

    def __call__(self, request: HttpRequest):
        result = super().__call__(request)
        if result is not None:
            if self.permission == "any":
                return result
            if self.permission == "is_authenticated" and request.user.is_authenticated:
                return result
            if (
                self.permission == "is_staff"
                and request.user.is_authenticated
                and request.user.is_staff
            ):
                return result
        return self.permission == "any"


# The lambda _: True is to handle the case where a user doesn't pass any authentication.
allow_any: list[Callable] = [django_auth, PermissionedTokenAuth("any", scope=[]), lambda _: True]
is_authenticated = [django_auth, PermissionedTokenAuth("is_authenticated", scope=[])]
is_staff = [SessionAuthStaffUser(), PermissionedTokenAuth("is_staff", scope=[])]
