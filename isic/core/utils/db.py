from contextlib import contextmanager

from django.db import models, transaction


@contextmanager
def lock_table(cls: type[models.Model]):
    with transaction.atomic():
        cursor = transaction.get_connection().cursor()
        cursor.execute(f"LOCK TABLE {cls._meta.db_table}")
        try:
            yield
        finally:
            cursor.close()
