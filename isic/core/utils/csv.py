from collections.abc import Iterable, Mapping
import csv
import re
from typing import Any, override

from django.core.validators import RegexValidator
from django.db.models import Q
from isic_metadata import FORBIDDEN_LEADING_CHARS

# See also:
# https://georgemauer.net/2017/10/07/csv-injection.html
# https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/CSV%20Injection/README.md
#
# A value is written to a CSV either through EscapingDictWriter, or unescaped after being validated
# to never start with one of FORBIDDEN_LEADING_CHARS, which isic-metadata does for structured
# metadata and the validator/constraint below do for everything else.


FORBIDDEN_LEADING_CHARS_REGEX = rf"^[{re.escape(''.join(FORBIDDEN_LEADING_CHARS))}]"

validate_no_forbidden_leading_char = RegexValidator(
    FORBIDDEN_LEADING_CHARS_REGEX,
    message=f"Cannot start with one of {' '.join(FORBIDDEN_LEADING_CHARS)}.",
    code="forbidden_leading_char",
    inverse_match=True,
)


def no_forbidden_leading_char_q(field_name: str) -> Q:
    """Build the condition of a CheckConstraint matching validate_no_forbidden_leading_char."""
    return ~Q(**{f"{field_name}__regex": FORBIDDEN_LEADING_CHARS_REGEX})


class EscapingDictWriter(csv.DictWriter):
    def _escape_value(self, value: Any) -> Any:
        if isinstance(value, str) and value.startswith(FORBIDDEN_LEADING_CHARS):
            return "\t" + value
        return value

    @override
    def writerow(self, row: Mapping[Any, Any]):
        escaped_row = {key: self._escape_value(value) for key, value in row.items()}
        return super().writerow(escaped_row)

    @override
    def writerows(self, rows: Iterable[Mapping[Any, Any]]) -> None:
        for row in rows:
            self.writerow(row)
