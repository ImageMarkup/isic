from collections.abc import Iterable
import time


def throttled_iterator(iterable: Iterable, max_per_second: int = 100) -> Iterable:
    for item in iterable:
        yield item
        time.sleep(1 / max_per_second)
