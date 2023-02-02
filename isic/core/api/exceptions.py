from rest_framework.exceptions import APIException


class Conflict(APIException):
    status_code = 409
    default_detail = "Request conflicts with current state of the target resource."
    default_code = "conflict"
