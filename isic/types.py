from typing import Any

from django.contrib.auth.models import User
from django.http import HttpRequest


class AuthenticatedHttpRequest(HttpRequest):
    user: User


class NinjaAuthHttpRequest(HttpRequest):
    auth: Any
