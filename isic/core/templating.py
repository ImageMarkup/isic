import logging
import traceback

from django.conf import settings

"""
This file is for providing more safety around potentially undefined template variables.
It's directly inspired by https://adamj.eu/tech/2022/03/30/how-to-make-django-error-for-undefined-template-variables/#with-a-logging-filter-that-raises-exceptions.

Due to how Django and the ecosystem treat missing template variables, certain paths have to be
ignored.
"""


class MissingVariableError(Exception):
    """
    A variable was missing from a template.

    Used as an alternative to VariableDoesNotExist, because that exception has some
    meaning within the template engine.
    """


class MissingVariableErrorFilter(logging.Filter):
    """
    Escalate missing variable log messages.

    Take log messages from Django for missing template variables and turn them
    into exceptions if the setting RAISE_MISSING_TEMPLATE_VARIABLES is True. Otherwise,
    promote them into ERROR level log messages which can be easily caught by Sentry.
    """

    ignored_prefixes = (
        "admin/",
        "auth/",
        "debug_toolbar/",
        "django/",
    )

    def _originates_from_ninja(self) -> bool:
        """
        Check if the log message originates from the ninja schema.

        This is necessary because django-ninja uses the same variable resolver API that
        emits VariableDoesNotExist errors for its serialization.
        """
        stack = traceback.extract_stack()
        return any(frame.filename.endswith("ninja/schema.py") for frame in stack)

    def filter(self, record):
        if record.msg.startswith("Exception while resolving variable "):
            variable_name, template_name = record.args
            if (
                not template_name.startswith(self.ignored_prefixes)
                and not self._originates_from_ninja()
            ):
                if settings.RAISE_MISSING_TEMPLATE_VARIABLES:
                    raise MissingVariableError(
                        f"{variable_name!r} missing in {template_name!r}"
                    ) from None
                else:
                    record.level = logging.ERROR
                    return True

        return False
