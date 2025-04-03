from collections.abc import Iterable, Mapping
import csv
from typing import Any, Final, override

# See also:
# https://georgemauer.net/2017/10/07/csv-injection.html
# https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/CSV%20Injection/README.md


FORBIDDEN_LEADING_CHARS: Final = ("=", "-", "+", "@")


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
    def writerows(self, rows: Iterable[Mapping[Any, Any]]):
        return map(self.writerow, rows)
