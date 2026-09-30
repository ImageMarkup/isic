from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from isic.core.dsl import SearchQueryParseError


def exception_handler(exc, context):
    # s3_file_field serves DRF views of its own, and its client expects DRF's responses.
    if not context["view"].__module__.startswith("isic."):
        return drf_exception_handler(exc, context)

    headers = {}

    if isinstance(exc, exceptions.NotAuthenticated | exceptions.AuthenticationFailed):
        data, status_code = {"detail": "Unauthorized"}, status.HTTP_401_UNAUTHORIZED
        if auth_header := getattr(exc, "auth_header", None):
            headers["WWW-Authenticate"] = auth_header
    elif isinstance(exc, Http404 | exceptions.NotFound):
        data, status_code = {"detail": "Not Found"}, status.HTTP_404_NOT_FOUND
    elif isinstance(exc, exceptions.ParseError):
        data, status_code = {"detail": "Cannot parse request body"}, status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, exceptions.ValidationError):
        data, status_code = {"detail": exc.detail}, status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, DjangoValidationError):
        # messages rather than message, since a ValidationError raised by full_clean carries a
        # dict of per field errors and has no .message at all.
        data, status_code = {"message": "; ".join(exc.messages)}, status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, SearchQueryParseError):
        data, status_code = (
            {"message": "Could not parse search query."},
            status.HTTP_400_BAD_REQUEST,
        )
    else:
        return drf_exception_handler(exc, context)

    return Response(data, status=status_code, headers=headers)
